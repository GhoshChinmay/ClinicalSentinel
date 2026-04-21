"""
DataSentinel — Natural Language Query Engine (Groq Cloud-Accelerated)
Translates English to SQL via Groq/Llama 3.3 70B and executes against DuckDB.

PRIVACY GUARANTEE: Only the schema string and user query text are sent to Groq.
Raw row data never leaves the local machine.
"""

import os
import re
import json
import asyncio
import polars as pl
import duckdb

from utils import _session_dir, logger, _BACKEND_DIR, log_audit_action
from groq_client import groq_chat, MODEL_REASONING


def _sanitize_llm_sql(raw_response: str) -> str:
    """Aggressively strips markdown and conversational English from the LLM's response."""
    import re
    
    # 1. Remove markdown blocks if present
    match = re.search(r"```(?:sql)?\n(.*?)```", raw_response, re.DOTALL)
    if match:
        raw_response = match.group(1)
        
    # 2. Extract only valid SQL commands using Regex
    # This finds lines starting with SELECT, UPDATE, or DELETE
    statements = re.findall(r"\b(SELECT\s+.*|UPDATE\s+.*|DELETE\s+FROM\s+.*)", raw_response, re.IGNORECASE)
    
    if statements:
        # Grab the LAST statement found (often the AI corrects itself at the end)
        best_sql = statements[-1]
        
        # Cut off the string at the first semicolon to ignore trailing English
        best_sql = best_sql.split(';')[0]
        
        # Extra safety: split on common English words that ruin syntax
        best_sql = re.split(r'\bis not\b|\binstead\b|\bhere is\b|\bthis is\b', best_sql, flags=re.IGNORECASE)[0]
        
        # Ensure proper DuckDB quotes
        best_sql = best_sql.replace('`', '"')
        
        return best_sql.strip()
        
    # Fallback if regex fails
    fallback = raw_response.replace('\n', ' ').replace(';', '').strip()
    return fallback.replace('`', '"')


def _force_try_cast(sql: str) -> str:
    """Replace all CAST(...) with TRY_CAST(...) to prevent DuckDB conversion errors on dirty data."""
    result = re.sub(r"\bCAST\s*\(", "TRY_CAST(", sql, flags=re.IGNORECASE)
    result = result.replace("TRY_TRY_CAST", "TRY_CAST")
    
    # Catch Postgres-style casts (e.g. rating::DOUBLE -> TRY_CAST(rating AS DOUBLE))
    result = re.sub(r"([a-zA-Z0-9_]+)::([a-zA-Z0-9_]+)", r"TRY_CAST(\1 AS \2)", result)
    
    # Fix pythonic/Polars types that duckdb rejects
    result = re.sub(r"\bFLOAT64\b", "DOUBLE", result, flags=re.IGNORECASE)
    result = re.sub(r"\bINT64\b", "BIGINT", result, flags=re.IGNORECASE)
    result = re.sub(r"\bFLOAT32\b", "FLOAT", result, flags=re.IGNORECASE)
    result = re.sub(r"\bINT32\b", "INTEGER", result, flags=re.IGNORECASE)
    return result


# ─── CONVERSATIONAL MEMORY HELPERS ───────────────────────────────────────────
def _get_chat_history(session_dir: str) -> list:
    """Loads recent chat history from the session directory."""
    history_path = os.path.join(session_dir, "chat_history.json")
    if os.path.exists(history_path):
        try:
            with open(history_path, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_chat_history(session_dir: str, history: list):
    """Saves chat history, keeping only the last 6 interactions to prevent prompt bloat."""
    history_path = os.path.join(session_dir, "chat_history.json")
    with open(history_path, "w") as f:
        # Save only the last 6 messages (3 turns) to save context tokens
        json.dump(history[-6:], f)
# ─────────────────────────────────────────────────────────────────────────────


async def execute_natural_query_stream(session_id: str, user_query: str, is_edit: bool = False):
    """Executes a query and streams progress updates using Server-Sent Events (SSE)."""
    session_dir = _session_dir(session_id)
    
    # ── STEP 4.1: LIVE DATABASE CHECK ──
    config_path = os.path.join(session_dir, "db_config.json")
    is_live_db = os.path.exists(config_path)
    db_uri = None
    
    if is_live_db:
        with open(config_path, "r") as f:
            db_uri = json.load(f).get("db_uri")
        yield f"data: {json.dumps({'status': 'Connecting to live PostgreSQL instance...'})}\n\n"
    else:
        cleaned_path = f"{session_dir}/cleaned_data.parquet"
        raw_path = f"{session_dir}/raw_data.parquet"
        data_path = cleaned_path if os.path.exists(cleaned_path) else raw_path

        if not os.path.exists(data_path):
            yield f"data: {json.dumps({'error': 'Dataset not found. Please upload a file or connect a database.'})}\n\n"
            return

    # Reflecting knowledge retrieval in the status
    yield f"data: {json.dumps({'status': 'Analyzing schema and retrieving business context...'})}\n\n"
    await asyncio.sleep(0.1)

    try:
        # Fetch relevant business rules from Knowledge Base (RAG Step)
        business_context = _get_business_context(user_query)
        schema_str = ""

        # ── DYNAMIC SCHEMA EXTRACTION ──
        if is_live_db:
            # Read schema directly from PostgreSQL using DuckDB
            con = duckdb.connect()
            con.execute("INSTALL postgres; LOAD postgres;")
            con.execute(f"ATTACH '{db_uri}' AS live_db (TYPE POSTGRES);")
            
            tables_df = con.query("SELECT table_name FROM live_db.information_schema.tables WHERE table_schema='public'").pl()
            schema_parts = []
            
            for t in tables_df['table_name']:
                cols = con.query(f"SELECT column_name, data_type FROM live_db.information_schema.columns WHERE table_name='{t}'").pl()
                col_strs = [f"{r['column_name']} ({r['data_type']})" for r in cols.to_dicts()]
                schema_parts.append(f"Table '{t}': " + ", ".join(col_strs))
            
            schema_str = "\n".join(schema_parts)
            con.close()
        else:
            # ── METADATA CACHING LAYER (Parquet File Mode) ──
            metadata_path = os.path.join(session_dir, "metadata.json")
            schema_parts = []
            
            if os.path.exists(metadata_path):
                # Fast Path: Read 1KB JSON instead of 500MB Parquet
                with open(metadata_path, "r") as f:
                    meta = json.load(f)
                for col, dtype in zip(meta.get("columns", []), meta.get("dtypes", [])):
                    schema_parts.append(f"{col} ({dtype})")
            else:
                # Slow Path: Fallback to reading the actual file if cache is missing
                df = pl.read_parquet(data_path)
                for col, dtype in zip(df.columns, df.dtypes):
                    type_str = str(dtype)
                    if dtype in [pl.Utf8, getattr(pl, "String", pl.Utf8)]:
                        sample = df[col].drop_nulls()
                        if len(sample) > 0:
                            try:
                                stripped = sample.str.replace_all(r"[₹$€£¥,%\s]", "").str.strip_chars()
                                numeric_ratio = stripped.str.contains(r"^-?\d+\.?\d*$").sum() / len(sample)
                                if numeric_ratio > 0.3:
                                    type_str += f" [WARNING: ~{numeric_ratio:.0%} values are numeric-like, use TRY_CAST]"
                            except Exception:
                                pass
                    schema_parts.append(f"{col} ({type_str})")

            schema_str = f"Table 'my_table': " + ", ".join(schema_parts)

        # ── SEPARATED PROMPT ARCHITECTURE ──
        system_prompt = f"""You are an expert SQL Data Analyst working with DuckDB.
The database schema is:
{schema_str}

{business_context}

CRITICAL RULES:
1. TYPE SAFETY: NEVER use string functions like REGEXP_REPLACE on columns that are already numeric (DOUBLE, BIGINT, INTEGER). Only use REGEXP_REPLACE on VARCHAR/String columns if you need to extract numbers.
2. NEVER use CAST(). ALWAYS use TRY_CAST() instead.
3. Handle NULL values gracefully.
4. Use LIMIT 100 for SELECT queries unless explicitly asked for all.
5. ALWAYS quote column names with double quotes ("column name"). NEVER use backticks (`).
"""
        # Dynamic Prompting based on DB vs File
        if is_live_db:
            system_prompt += "\n6. You are querying a live PostgreSQL database. Ensure your SQL is compatible with standard Postgres syntax. Do not write CREATE VIEW or ATTACH commands."
        else:
            system_prompt += "\n6. Table name MUST be exactly: 'my_table'."

        if is_edit:
            system_prompt += "\nReturn ONLY a valid SQL UPDATE or DELETE statement. Start strictly with UPDATE or DELETE. No conversational text."
        else:
            system_prompt += "\nReturn ONLY a valid SQL SELECT statement. Start strictly with SELECT. No conversational text."

        yield f"data: {json.dumps({'status': 'Consulting Groq Llama 3.3 for SQL generation...'})}\n\n"
        await asyncio.sleep(0.1)

        # ── INJECTING MEMORY ──
        messages = [{"role": "system", "content": system_prompt}]
        chat_history = _get_chat_history(session_dir)
        messages.extend(chat_history)
        messages.append({"role": "user", "content": user_query})

        last_error = None
        sql_query = ""

        for attempt in range(2):
            raw_response = groq_chat(
                messages=messages,
                model=MODEL_REASONING,
                temperature=0.1,
                max_tokens=1024,
                timeout=15,
            )

            if raw_response is None:
                yield f"data: {json.dumps({'error': 'AI query generation failed. Groq API may be unavailable.'})}\n\n"
                return

            sql_query = _sanitize_llm_sql(raw_response)
            sql_query = _force_try_cast(sql_query)

            logger.info("SQL Attempt %d: %s", attempt + 1, sql_query)

            yield f"data: {json.dumps({'status': f'Executing SQL against Database (Attempt {attempt + 1})...', 'sql': sql_query})}\n\n"
            await asyncio.sleep(0.1)

            if is_edit:
                upper = sql_query.strip().upper()
                if not upper.startswith("UPDATE") and not upper.startswith("DELETE"):
                    yield f"data: {json.dumps({'error': f'Expected UPDATE or DELETE statement, got: {sql_query[:50]}...'})}\n\n"
                    return
                yield f"data: {json.dumps({'status': 'Complete', 'sql': sql_query})}\n\n"
                return
            else:
                upper = sql_query.strip().upper()
                if not upper.startswith("SELECT"):
                    yield f"data: {json.dumps({'error': f'Expected SELECT statement, got: {sql_query[:50]}...'})}\n\n"
                    return
                
                con = None
                try:
                    con = duckdb.connect()
                    
                    # ── ATTACH DB OR PARQUET FOR EXECUTION ──
                    if is_live_db:
                        con.execute("INSTALL postgres; LOAD postgres;")
                        con.execute(f"ATTACH '{db_uri}' AS live_db (TYPE POSTGRES);")
                        con.execute("USE live_db;")
                    else:
                        con.execute(f"CREATE VIEW my_table AS SELECT * FROM '{data_path}'")
                        
                    result_df = con.query(sql_query).pl()
                    
                    # ── PHASE 2.0: SEMANTIC REFLECTION (Empty Result Check) ──
                    if len(result_df) == 0 and attempt == 0 and not is_edit:
                        logger.info("Query succeeded but returned 0 rows. Triggering Reflection...")
                        
                        yield f"data: {json.dumps({'status': 'Query returned 0 rows. Reflecting and broadening search criteria...'})}\n\n"
                        await asyncio.sleep(0.1)
                        
                        messages.append({"role": "assistant", "content": raw_response})
                        messages.append({
                            "role": "user", 
                            "content": "The query executed successfully but returned 0 rows. The filters might be too strict, case-sensitive, or the category might not exist exactly as spelled. Rewrite the query to be more forgiving (e.g., use ILIKE '%keyword%', LOWER(), or remove strict AND conditions)."
                        })
                        continue # Force the loop to run Attempt #2
                        
                    # ── SAVE TO MEMORY AFTER SUCCESS ──
                    chat_history.append({"role": "user", "content": user_query})
                    chat_history.append({"role": "assistant", "content": f"I executed: {sql_query}"}) 
                    _save_chat_history(session_dir, chat_history)

                    # ── OPTION 2: GENERATE NEXT BEST ACTIONS ──
                    yield f"data: {json.dumps({'status': 'Data retrieved. Generating follow-up suggestions...'})}\n\n"
                    
                    suggestion_prompt = f"""Based on the user's query: "{user_query}"
And the resulting columns: {list(result_df.columns)}
Generate exactly 3 short, analytical follow-up questions the user should ask next.
Return ONLY a valid JSON array of 3 strings. Example: ["Group these by region", "What is the average amount?"]"""

                    try:
                        # Use a faster, cheaper model for suggestions (e.g., llama3-8b-8192)
                        sugg_response = groq_chat([{"role": "user", "content": suggestion_prompt}], model="llama3-8b-8192", temperature=0.7)
                        
                        # Clean markdown and parse
                        clean_sugg = sugg_response.replace("```json", "").replace("```", "").strip()
                        suggestions = json.loads(clean_sugg)
                    except Exception as e:
                        logger.warning(f"Failed to generate suggestions: {e}")
                        suggestions = [] # Fail gracefully

                    # If we have data, or it's our last attempt, return the payload
                    final_payload = {
                        "status": "Complete",
                        "sql": sql_query,
                        "columns": result_df.columns,
                        "data": result_df.head(100).to_dicts(),
                        "suggestions": suggestions[:3] # Ensure max 3
                    }
                    yield f"data: {json.dumps(final_payload)}\n\n"
                    return
                
                except Exception as e:
                    last_error = str(e)
                    # DuckDB throws specific errors for Postgres connection/syntax issues
                    if "Conversion Error" in last_error or "Binder Error" in last_error or "Catalog Error" in last_error or "syntax error" in last_error.lower():
                        logger.warning("SQL crashed. Triggering Auto-Correction. Error: %s", last_error)
                        
                        yield f"data: {json.dumps({'status': 'Crash detected. Triggering self-correction loop...', 'error_detail': last_error})}\n\n"
                        await asyncio.sleep(0.1)
                        
                        messages.append({"role": "assistant", "content": raw_response})
                        messages.append({
                            "role": "user", 
                            "content": f"Your query crashed with this database error:\n{last_error}\n\nRewrite the query. CRITICAL: You MUST use TRY_CAST(column AS DOUBLE) when doing math/comparisons on dirty columns. Do NOT use backticks for column names."
                        })
                        continue
                    else:
                        yield f"data: {json.dumps({'error': f'Failed to execute. SQL: {sql_query} | Error: {last_error}'})}\n\n"
                        return
                finally:
                    if con:
                        con.close()

        yield f"data: {json.dumps({'error': f'AI Auto-correction failed after 2 attempts. Last Error: {last_error} | Last SQL: {sql_query}'})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'error': f'Failed to generate SQL: {str(e)}'})}\n\n"


def confirm_and_execute_edit(session_id: str, sql_query: str):
    session_dir = _session_dir(session_id)
    cleaned_path = f"{session_dir}/cleaned_data.parquet"
    raw_path = f"{session_dir}/raw_data.parquet"
    data_path = cleaned_path if os.path.exists(cleaned_path) else raw_path

    # ── CHECK FOR LIVE DB ──
    config_path = os.path.join(session_dir, "db_config.json")
    is_live_db = os.path.exists(config_path)
    db_uri = None
    if is_live_db:
        with open(config_path, "r") as f:
            db_uri = json.load(f).get("db_uri")

    con = None
    try:
        con = duckdb.connect()
        
        # ── ATTACH DB OR PARQUET ──
        if is_live_db:
            con.execute("INSTALL postgres; LOAD postgres;")
            con.execute(f"ATTACH '{db_uri}' AS live_db (TYPE POSTGRES);")
            con.execute("USE live_db;")
        else:
            con.execute(f"CREATE TABLE my_table AS SELECT * FROM '{data_path}'")

        clean_sql = sql_query.strip().rstrip(";")
        clean_sql = _force_try_cast(clean_sql)

        # BUG-09 FIX: SQL injection guard — block dangerous DDL/DML and multi-statement injection
        _FORBIDDEN_PATTERNS = re.compile(
            r"\b(DROP|CREATE|ALTER|COPY|ATTACH|DETACH|PRAGMA|VACUUM|ANALYZE|GRANT|REVOKE|TRUNCATE)\b",
            re.IGNORECASE,
        )
        if _FORBIDDEN_PATTERNS.search(clean_sql):
            return {
                "error": "Forbidden SQL statement type. Only UPDATE and DELETE are permitted."
            }
        if ";" in clean_sql:
            return {"error": "Multi-statement SQL is not allowed."}

        upper = clean_sql.strip().upper()

        if upper.startswith("DELETE"):
            try:
                # Attempt to get row count if my_table exists (local parquet)
                before_count = con.execute("SELECT COUNT(*) FROM my_table").fetchone()[0]
                con.execute(clean_sql)
                after_count = con.execute("SELECT COUNT(*) FROM my_table").fetchone()[0]
                rows_affected = before_count - after_count
            except Exception:
                # Fallback for live DB where 'my_table' isn't used
                con.execute(clean_sql)
                rows_affected = 0 # Postgres extension handles execution directly

            if not is_live_db:
                con.execute(f"COPY my_table TO '{data_path}' (FORMAT PARQUET)")
                preview_df = con.query("SELECT * FROM my_table LIMIT 50").pl()
            else:
                preview_df = pl.DataFrame() # Live DB preview omitted for safety

            # ── NEW: LOG THE DELETE ACTION ──
            log_audit_action(session_id, "User confirmed DELETE execution", clean_sql, rows_affected, "success")

            return {
                "status": "success",
                "rows_affected": rows_affected,
                "columns": preview_df.columns if not is_live_db else [],
                "preview_data": preview_df.head(50).to_dicts() if not is_live_db else [],
            }

        elif upper.startswith("UPDATE"):
            try:
                if not clean_sql.upper().rstrip().endswith("RETURNING *") and not is_live_db:
                    returning_sql = clean_sql + " RETURNING *"
                else:
                    returning_sql = clean_sql
                affected_df = con.query(returning_sql).pl()
                rows_affected = len(affected_df)
            except Exception:
                con.execute(clean_sql)
                rows_affected = 0
                affected_df = con.query("SELECT * FROM my_table LIMIT 50").pl() if not is_live_db else pl.DataFrame()

            if not is_live_db:
                con.execute(f"COPY my_table TO '{data_path}' (FORMAT PARQUET)")

            # ── NEW: LOG THE UPDATE ACTION ──
            log_audit_action(session_id, "User confirmed UPDATE execution", clean_sql, rows_affected, "success")

            return {
                "status": "success",
                "rows_affected": rows_affected,
                "columns": affected_df.columns if not is_live_db else [],
                "preview_data": affected_df.head(50).to_dicts() if not is_live_db else [],
            }
        else:
            return {"error": f"Expected UPDATE or DELETE, got: {clean_sql[:50]}"}

    except Exception as e:
        error_str = str(e)
        
        # ── NEW: LOG THE FAILED ACTION ──
        log_audit_action(session_id, "User confirmed execution (FAILED)", sql_query, 0, "failed", error_str)
        
        if "Conversion Error" in error_str:
            return {
                "error": f"Type conversion error on dirty data. Hint: The column contains mixed types (text + numbers). DuckDB: {error_str}"
            }
        return {"error": error_str}
    finally:
        if con:
            con.close()

def _get_business_context(user_query: str) -> str:
    """
    Enhanced Retrieval: Matches user intent against the Knowledge Base categories.
    """
    import json
    dict_path = os.path.join(_BACKEND_DIR, "data", "business_dictionary.json")
    if not os.path.exists(dict_path):
        return ""

    with open(dict_path, "r") as f:
        kb = json.load(f).get("knowledge_base", {})

    found_rules = []
    query_norm = user_query.lower()

    # Iterate through all domains (financial, quality, temporal, etc.)
    for domain, rules in kb.items():
        for rule in rules:
            # Check if the term or any keyword is in the query
            match_term = rule["term"].lower() in query_norm
            match_keywords = any(kw in query_norm for kw in rule.get("keywords", []))
            
            if match_term or match_keywords:
                found_rules.append(f"[{rule['term']}]: {rule['logic']} ({rule['description']})")

    if not found_rules:
        return ""

    return "\nRELEVANT KNOWLEDGE BASE RULES:\n" + "\n".join(found_rules)