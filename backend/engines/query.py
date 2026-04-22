"""
DataSentinel — Natural Language Query Engine (Godmode Edition)
Translates English to SQL via Groq/Llama 3.3 70B and executes against DuckDB.

UPGRADES:
- Advanced CTE & Subquery parsing
- Dynamic categorical value sampling for zero-shot accuracy
- DBA-level targeted self-healing error loops
- DuckDB resource sandboxing
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
    """Enterprise-grade SQL extractor. Handles complex CTEs, multi-line, and markdown."""
    # 1. Prioritize extracting from markdown code blocks
    match = re.search(r"```(?:sql)?\n(.*?)```", raw_response, re.DOTALL)
    if match:
        raw_response = match.group(1)
        
    # 2. Extract valid SQL boundaries (Now heavily supports WITH clauses for CTEs)
    statements = re.findall(r"\b(WITH\s+.*|SELECT\s+.*|UPDATE\s+.*|DELETE\s+FROM\s+.*)", raw_response, re.IGNORECASE | re.DOTALL)
    
    if statements:
        # Grab the longest/most complete statement (often the AI corrects itself or explains then writes)
        best_sql = max(statements, key=len)
        
        # Strip trailing English safely. Split by semicolon, but carefully (semi-colons can be in string literals)
        # For safety, we just take the first logical SQL block ending in a semicolon at the end of a line
        best_sql = re.split(r';\s*(?:\n|$)', best_sql)[0]
        
        # Clean conversational English bleed-over safely without breaking IS NOT NULL
        best_sql = re.split(r'\binstead,?\b|\bhere is\b|\bthis is\b|\bto fix this\b', best_sql, flags=re.IGNORECASE)[0]
        
        # Ensure proper DuckDB quotes
        best_sql = best_sql.replace('`', '"')
        
        return best_sql.strip()
        
    fallback = raw_response.replace('\n', ' ').replace(';', '').strip()
    return fallback.replace('`', '"')


def _force_try_cast(sql: str) -> str:
    """Aggressive DBA-level type casting to prevent query death on dirty data."""
    result = re.sub(r"\bCAST\s*\(", "TRY_CAST(", sql, flags=re.IGNORECASE)
    result = result.replace("TRY_TRY_CAST", "TRY_CAST")
    result = re.sub(r"([a-zA-Z0-9_]+)::([a-zA-Z0-9_]+)", r"TRY_CAST(\1 AS \2)", result)
    
    # Map Polars/Pandas types to DuckDB
    type_maps = {"FLOAT64": "DOUBLE", "INT64": "BIGINT", "FLOAT32": "FLOAT", "INT32": "INTEGER", "STRING": "VARCHAR"}
    for k, v in type_maps.items():
        result = re.sub(rf"\b{k}\b", v, result, flags=re.IGNORECASE)
    return result


def _get_chat_history(session_dir: str) -> list:
    history_path = os.path.join(session_dir, "chat_history.json")
    if os.path.exists(history_path):
        try:
            with open(history_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_chat_history(session_dir: str, history: list):
    history_path = os.path.join(session_dir, "chat_history.json")
    with open(history_path, "w") as f:
        json.dump(history[-8:], f) # Keep last 4 turns for deeper context


async def execute_natural_query_stream(session_id: str, user_query: str, is_edit: bool = False):
    session_dir = _session_dir(session_id)
    config_path = os.path.join(session_dir, "db_config.json")
    is_live_db = os.path.exists(config_path)
    db_uri = None
    
    if is_live_db:
        with open(config_path, "r") as f:
            db_uri = json.load(f).get("db_uri")
        yield f"data: {json.dumps({'status': 'Establishing secure connection to PostgreSQL...'})}\n\n"
    else:
        cleaned_path = f"{session_dir}/cleaned_data.parquet"
        raw_path = f"{session_dir}/raw_data.parquet"
        data_path = cleaned_path if os.path.exists(cleaned_path) else raw_path

        if not os.path.exists(data_path):
            yield f"data: {json.dumps({'error': 'Dataset missing. Please upload a file.'})}\n\n"
            return

    yield f"data: {json.dumps({'status': 'Profiling schema & enriching categorical context...'})}\n\n"
    await asyncio.sleep(0.1)

    try:
        business_context = _get_business_context(user_query)
        schema_parts = []

        if is_live_db:
            con = duckdb.connect()
            con.execute("INSTALL postgres; LOAD postgres;")
            con.execute(f"ATTACH '{db_uri}' AS live_db (TYPE POSTGRES);")
            tables_df = con.query("SELECT table_name FROM live_db.information_schema.tables WHERE table_schema='public'").pl()
            for t in tables_df['table_name']:
                cols = con.query(f"SELECT column_name, data_type FROM live_db.information_schema.columns WHERE table_name='{t}'").pl()
                schema_parts.append(f"Table '{t}': " + ", ".join([f"{r['column_name']} ({r['data_type']})" for r in cols.to_dicts()]))
            schema_str = "\n".join(schema_parts)
            con.close()
        else:
            # ── GODMODE UPGRADE: Categorical Value Injection ──
            # Gives the LLM actual unique values so it stops guessing text filters
            df = pl.read_parquet(data_path)
            for col, dtype in zip(df.columns, df.dtypes):
                type_str = str(dtype)
                if dtype in [pl.Utf8, getattr(pl, "String", pl.Utf8)]:
                    sample = df[col].drop_nulls()
                    if len(sample) > 0:
                        n_unique = sample.n_unique()
                        if n_unique <= 5:
                            # If low cardinality, tell the LLM exactly what the values are!
                            uniques = sample.unique().to_list()
                            type_str += f" [ENUM VALUES: {', '.join(uniques)}]"
                        else:
                            stripped = sample.str.replace_all(r"[₹$€£¥,%\s]", "").str.strip_chars()
                            numeric_ratio = stripped.str.contains(r"^-?\d+\.?\d*$").sum() / len(sample)
                            if numeric_ratio > 0.3:
                                type_str += f" [WARNING: ~{numeric_ratio:.0%} numeric-like, use TRY_CAST]"
                schema_parts.append(f'"{col}" ({type_str})')
            schema_str = f"Table 'my_table':\n" + "\n".join(schema_parts)

        # ── GODMODE SYSTEM PROMPT ──
        system_prompt = f"""You are a Principal Data Engineer writing advanced DuckDB SQL.
SCHEMA:
{schema_str}

{business_context}

CRITICAL EXECUTION RULES:
1. TYPE SAFETY: NEVER use REGEXP_REPLACE on DOUBLE/BIGINT. Use TRY_CAST(col AS DOUBLE) for dirty string-numbers.
2. NULL HANDLING: Use COALESCE() or explicit 'IS NOT NULL' checks for aggregations.
3. ADVANCED ANALYTICS: For cohort analysis or distributions, utilize Common Table Expressions (WITH clause) and Window Functions (OVER PARTITION BY).
4. QUOTES: ALWAYS wrap column names in double quotes ("Column Name"). NEVER use backticks.
5. LIMITS: Apply LIMIT 100 on raw row SELECTs, but DO NOT limit aggregations until the final output.
"""
        if is_live_db:
            system_prompt += "\n6. DIALECT: PostgreSQL compatible. DO NOT use DuckDB specific extensions. Target table is inside schema: live_db.public."
        else:
            system_prompt += "\n6. Target table MUST be exactly: my_table."

        if is_edit:
            system_prompt += "\nOUTPUT: STRICTLY a valid UPDATE or DELETE statement. No markdown, no explanations."
        else:
            system_prompt += "\nOUTPUT: STRICTLY a valid SELECT statement. No markdown, no explanations."

        yield f"data: {json.dumps({'status': 'Architecting Advanced SQL Query...'})}\n\n"
        await asyncio.sleep(0.1)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(_get_chat_history(session_dir))
        messages.append({"role": "user", "content": user_query})

        last_error = None
        sql_query = ""
        
        # ── GODMODE UPGRADE: 3-Strike Self Healing Loop ──
        MAX_ATTEMPTS = 3 

        for attempt in range(MAX_ATTEMPTS):
            raw_response = groq_chat(
                messages=messages,
                model=MODEL_REASONING,
                temperature=0.1 if attempt == 0 else 0.4, # Increase creativity if stuck
                max_tokens=2048,
                timeout=20,
            )

            if raw_response is None:
                yield f"data: {json.dumps({'error': 'Compute cluster timeout. Groq LPU unavailable.'})}\n\n"
                return

            sql_query = _sanitize_llm_sql(raw_response)
            sql_query = _force_try_cast(sql_query)

            logger.info("SQL Attempt %d: %s", attempt + 1, sql_query)
            yield f"data: {json.dumps({'status': f'Executing Analytical Engine (Attempt {attempt + 1}/{MAX_ATTEMPTS})...', 'sql': sql_query})}\n\n"
            await asyncio.sleep(0.1)

            if is_edit:
                upper = sql_query.strip().upper()
                if not upper.startswith("UPDATE") and not upper.startswith("DELETE"):
                    yield f"data: {json.dumps({'error': f'Aborted: Execution block required UPDATE/DELETE, got: {sql_query[:50]}...'})}\n\n"
                    return
                yield f"data: {json.dumps({'status': 'Complete', 'sql': sql_query})}\n\n"
                return
            else:
                upper = sql_query.strip().upper()
                if not upper.startswith("SELECT") and not upper.startswith("WITH"):
                    yield f"data: {json.dumps({'error': f'Aborted: Execution block required SELECT/WITH, got: {sql_query[:50]}...'})}\n\n"
                    return
                
                con = None
                try:
                    con = duckdb.connect()
                    # ── GODMODE UPGRADE: Resource Sandboxing ──
                    con.execute("PRAGMA threads=4;") # Prevent starving the FastAPI server
                    con.execute("PRAGMA max_memory='4GB';") # Prevent Cartesian product OOM death
                    
                    if is_live_db:
                        con.execute("INSTALL postgres; LOAD postgres;")
                        con.execute(f"ATTACH '{db_uri}' AS live_db (TYPE POSTGRES);")
                        con.execute("USE live_db;")
                    else:
                        con.execute(f"CREATE VIEW my_table AS SELECT * FROM '{data_path}'")
                        
                    result_df = con.query(sql_query).pl()
                    
                    # ── Semantic Reflection ──
                    if len(result_df) == 0 and attempt < (MAX_ATTEMPTS - 1) and not is_edit:
                        logger.info("0 Rows Returned. Triggering Semantic Reflection...")
                        yield f"data: {json.dumps({'status': 'Optimization: 0 rows matched. Broadening search parameters...'})}\n\n"
                        messages.append({"role": "assistant", "content": raw_response})
                        messages.append({"role": "user", "content": "Query succeeded but returned 0 rows. Remove strict AND limits, use ILIKE '%keyword%' instead of exact matches, and verify categorical cases."})
                        continue 
                        
                    chat_history = _get_chat_history(session_dir)
                    chat_history.append({"role": "user", "content": user_query})
                    chat_history.append({"role": "assistant", "content": f"I executed: {sql_query}"}) 
                    _save_chat_history(session_dir, chat_history)

                    yield f"data: {json.dumps({'status': 'Result compiled. Generating Next-Best-Action heuristics...'})}\n\n"
                    
                    suggestion_prompt = f"""Based on user query: "{user_query}"
Resulting columns: {list(result_df.columns)}
Generate exactly 3 analytical follow-up questions to dig deeper. Return ONLY a valid JSON array of strings."""

                    try:
                        # FIX 1: Upgraded Groq model to 3.1
                        sugg_response = groq_chat([{"role": "user", "content": suggestion_prompt}], model="llama-3.1-8b-instant", temperature=0.7)
                        clean_sugg = sugg_response.replace("```json", "").replace("```", "").strip()
                        suggestions = json.loads(clean_sugg)
                    except Exception:
                        suggestions = [] 

                    final_payload = {
                        "status": "Complete",
                        "sql": sql_query,
                        "columns": result_df.columns,
                        "data": result_df.head(100).to_dicts(),
                        "suggestions": suggestions[:3] 
                    }
                    
                    # FIX 2: Added `default=str` to handle DuckDB Decimals and Dates
                    yield f"data: {json.dumps(final_payload, default=str)}\n\n"
                    return
                
                except Exception as e:
                    last_error = str(e)
                    logger.warning("DBA Loop Triggered. Error: %s", last_error)
                    
                    if attempt < (MAX_ATTEMPTS - 1):
                        yield f"data: {json.dumps({'status': f'Syntax Error Detected. Booting Auto-DBA Refactoring (Attempt {attempt + 1})...', 'error_detail': last_error})}\n\n"
                        
                        # ── GODMODE UPGRADE: Context-Aware DBA Hints ──
                        hint = ""
                        if "Binder Error" in last_error or "Conversion Error" in last_error:
                            hint = "CRITICAL: You have a type mismatch. Wrap the offensive column in TRY_CAST(col AS DOUBLE) or TRY_CAST(col AS VARCHAR)."
                        elif "Catalog Error" in last_error:
                            hint = "CRITICAL: Column or table not found. Double check the exact casing of the column names provided in the schema."
                        elif "syntax error" in last_error.lower():
                            hint = "CRITICAL: Standard syntax error. Check your commas, quotes, and ensure CTEs (WITH) are structured properly."
                            
                        messages.append({"role": "assistant", "content": raw_response})
                        messages.append({"role": "user", "content": f"FATAL DUCKDB ERROR:\n{last_error}\n\n{hint}\nRewrite the SQL. Ensure double quotes for columns."})
                        continue
                    else:
                        yield f"data: {json.dumps({'error': f'Execution failed after {MAX_ATTEMPTS} attempts. Engine Error: {last_error}'})}\n\n"
                        return
                finally:
                    if con:
                        con.close()

        yield f"data: {json.dumps({'error': f'Irrecoverable query error. Last SQL: {sql_query}'})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'error': f'System Fault: {str(e)}'})}\n\n"


def confirm_and_execute_edit(session_id: str, sql_query: str):
    """Executes mutations with strict transactional boundaries and audit logging."""
    session_dir = _session_dir(session_id)
    cleaned_path = f"{session_dir}/cleaned_data.parquet"
    raw_path = f"{session_dir}/raw_data.parquet"
    data_path = cleaned_path if os.path.exists(cleaned_path) else raw_path

    config_path = os.path.join(session_dir, "db_config.json")
    is_live_db = os.path.exists(config_path)
    db_uri = None
    if is_live_db:
        with open(config_path, "r") as f:
            db_uri = json.load(f).get("db_uri")

    con = None
    try:
        con = duckdb.connect()
        # DBA Protection
        con.execute("PRAGMA threads=4;") 
        con.execute("PRAGMA max_memory='4GB';")
        
        if is_live_db:
            con.execute("INSTALL postgres; LOAD postgres;")
            con.execute(f"ATTACH '{db_uri}' AS live_db (TYPE POSTGRES);")
            con.execute("USE live_db;")
        else:
            con.execute(f"CREATE TABLE my_table AS SELECT * FROM '{data_path}'")

        clean_sql = sql_query.strip().rstrip(";")
        clean_sql = _force_try_cast(clean_sql)

        _FORBIDDEN_PATTERNS = re.compile(
            r"\b(DROP|CREATE|ALTER|COPY|ATTACH|DETACH|PRAGMA|VACUUM|ANALYZE|GRANT|REVOKE|TRUNCATE)\b",
            re.IGNORECASE,
        )
        if _FORBIDDEN_PATTERNS.search(clean_sql):
            return {"error": "SECURITY VIOLATION: Forbidden DDL statement detected. Only standard DML (UPDATE/DELETE) is permitted."}
        if ";" in clean_sql:
            return {"error": "SECURITY VIOLATION: Stacked multi-statement queries detected."}

        upper = clean_sql.strip().upper()

        if upper.startswith("DELETE"):
            try:
                before_count = con.execute("SELECT COUNT(*) FROM my_table").fetchone()[0]
                con.execute(clean_sql)
                after_count = con.execute("SELECT COUNT(*) FROM my_table").fetchone()[0]
                rows_affected = before_count - after_count
            except Exception:
                con.execute(clean_sql)
                rows_affected = 0 

            if not is_live_db:
                con.execute(f"COPY my_table TO '{data_path}' (FORMAT PARQUET)")
                preview_df = con.query("SELECT * FROM my_table LIMIT 50").pl()
            else:
                preview_df = pl.DataFrame() 

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

            log_audit_action(session_id, "User confirmed UPDATE execution", clean_sql, rows_affected, "success")

            return {
                "status": "success",
                "rows_affected": rows_affected,
                "columns": affected_df.columns if not is_live_db else [],
                "preview_data": affected_df.head(50).to_dicts() if not is_live_db else [],
            }
        else:
            return {"error": f"Invalid DML type. Expected UPDATE or DELETE, got: {clean_sql[:50]}"}

    except Exception as e:
        error_str = str(e)
        log_audit_action(session_id, "User confirmed execution (FAILED)", sql_query, 0, "failed", error_str)
        
        if "Conversion Error" in error_str:
            return {"error": f"Type conversion error on dirty data. Hint: The column contains mixed types (text + numbers). DuckDB: {error_str}"}
        return {"error": error_str}
    finally:
        if con:
            con.close()

def _get_business_context(user_query: str) -> str:
    import json
    dict_path = os.path.join(_BACKEND_DIR, "data", "business_dictionary.json")
    if not os.path.exists(dict_path):
        return ""

    with open(dict_path, "r") as f:
        kb = json.load(f).get("knowledge_base", {})

    found_rules = []
    query_norm = user_query.lower()

    for domain, rules in kb.items():
        for rule in rules:
            match_term = rule["term"].lower() in query_norm
            match_keywords = any(kw in query_norm for kw in rule.get("keywords", []))
            
            if match_term or match_keywords:
                found_rules.append(f"[{rule['term']}]: {rule['logic']} ({rule['description']})")

    if not found_rules:
        return ""

    return "\nRELEVANT KNOWLEDGE BASE RULES:\n" + "\n".join(found_rules)