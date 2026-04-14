"""
DataSentinel — Natural Language Query Engine (Groq Cloud-Accelerated)
Translates English to SQL via Groq/Llama 3.3 70B and executes against DuckDB.

PRIVACY GUARANTEE: Only the schema string and user query text are sent to Groq.
Raw row data never leaves the local machine.
"""

import os
import re
import polars as pl
import duckdb

from utils import _session_dir, logger
from groq_client import groq_chat, MODEL_REASONING


def _sanitize_llm_sql(raw_response: str) -> str:
    """Extract clean SQL from potentially messy LLM output."""
    match = re.search(r"```(?:sql)?\n(.*?)```", raw_response, re.DOTALL)
    if match:
        sql = match.group(1).strip()
    else:
        sql = raw_response.strip()

    for keyword in ["SELECT", "UPDATE", "DELETE"]:
        idx = sql.upper().find(keyword)
        if idx >= 0:
            sql = sql[idx:]
            break

    sql = sql.rstrip(";").strip()
    sql = re.sub(r"^```\s*", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"```\s*$", "", sql, flags=re.MULTILINE)

    return sql.strip()


def _force_try_cast(sql: str) -> str:
    """Replace all CAST(...) with TRY_CAST(...) to prevent DuckDB conversion errors on dirty data."""
    result = re.sub(r"\bCAST\s*\(", "TRY_CAST(", sql, flags=re.IGNORECASE)
    result = result.replace("TRY_TRY_CAST", "TRY_CAST")
    
    # NEW: Catch Postgres-style casts (e.g. rating::DOUBLE -> TRY_CAST(rating AS DOUBLE))
    result = re.sub(r"([a-zA-Z0-9_]+)::([a-zA-Z0-9_]+)", r"TRY_CAST(\1 AS \2)", result)
    
    # Fix pythonic/Polars types that duckdb rejects
    result = re.sub(r"\bFLOAT64\b", "DOUBLE", result, flags=re.IGNORECASE)
    result = re.sub(r"\bINT64\b", "BIGINT", result, flags=re.IGNORECASE)
    result = re.sub(r"\bFLOAT32\b", "FLOAT", result, flags=re.IGNORECASE)
    result = re.sub(r"\bINT32\b", "INTEGER", result, flags=re.IGNORECASE)
    return result


def execute_natural_query(session_id: str, user_query: str, is_edit: bool = False):
    session_dir = _session_dir(session_id)

    cleaned_path = f"{session_dir}/cleaned_data.parquet"
    raw_path = f"{session_dir}/raw_data.parquet"
    data_path = cleaned_path if os.path.exists(cleaned_path) else raw_path

    if not os.path.exists(data_path):
        return {"error": "Dataset not found."}

    try:
        df = pl.read_parquet(data_path)

        # Build a rich schema description including data quality warnings
        schema_parts = []
        for col, dtype in zip(df.columns, df.dtypes):
            type_str = str(dtype)
            if dtype in [pl.Utf8, getattr(pl, "String", pl.Utf8)]:
                sample = df[col].drop_nulls()
                if len(sample) > 0:
                    try:
                        stripped = sample.str.replace_all(
                            r"[₹$€£¥,%\s]", ""
                        ).str.strip_chars()
                        numeric_count = stripped.str.contains(r"^-?\d+\.?\d*$").sum()
                        numeric_ratio = numeric_count / len(sample)
                        if numeric_ratio > 0.3:
                            type_str += f" [WARNING: ~{numeric_ratio:.0%} values are numeric-like, use TRY_CAST]"
                    except Exception:
                        pass
            schema_parts.append(f"{col} ({type_str})")

        schema_str = ", ".join(schema_parts)

        system_prompt = f"""You are an expert SQL Data Analyst working with DuckDB.
The dataset schema is: {schema_str}
Table name MUST be exactly: 'my_table'
User request: "{user_query}"

CRITICAL RULES:
1. NEVER rely on implicit casting. If you do math or comparison (>, <, =, <=, >=) on a String/VARCHAR column, you MUST explicitly strip non-numeric characters first using REGEXP_REPLACE, then wrap in TRY_CAST. Example: TRY_CAST(REGEXP_REPLACE(column, '[^0-9.-]', '', 'g') AS DOUBLE).
2. NEVER use CAST(). ALWAYS use TRY_CAST() instead. This prevents crashes on mixed-type columns.
3. Handle NULL values gracefully — never assume a column is clean. When filtering on TRY_CAST, ensure the result IS NOT NULL before comparing.
4. Use LIMIT 100 for SELECT queries unless the user explicitly asks for all results.
5. Use standard SQL types for casting (e.g. DOUBLE, BIGINT, VARCHAR, BOOLEAN). Do not use Polars types like Float64 or Int64.
"""

        if is_edit:
            system_prompt += "\nReturn ONLY a valid SQL UPDATE or DELETE statement. Start strictly with UPDATE or DELETE. No conversational text."
        else:
            system_prompt += "\nReturn ONLY a valid SQL SELECT statement. Start strictly with SELECT. No conversational text."

        # ── NEW: Self-Healing Execution Loop ──
        messages = [{"role": "system", "content": system_prompt}]
        last_error = None
        sql_query = ""

        # Give the AI 2 attempts to get it right without crashing
        for attempt in range(2):
            raw_response = groq_chat(
                messages=messages,
                model=MODEL_REASONING,
                temperature=0.1,
                max_tokens=1024,
                timeout=15,
            )

            if raw_response is None:
                return {"error": "AI query generation failed. Groq API may be unavailable."}

            sql_query = _sanitize_llm_sql(raw_response)
            sql_query = _force_try_cast(sql_query)

            logger.info("SQL Attempt %d: %s", attempt + 1, sql_query)

            if is_edit:
                upper = sql_query.strip().upper()
                if not upper.startswith("UPDATE") and not upper.startswith("DELETE"):
                    return {"error": f"Expected UPDATE or DELETE statement, got: {sql_query[:50]}..."}
                return {"sql": sql_query}
            else:
                upper = sql_query.strip().upper()
                if not upper.startswith("SELECT"):
                    return {"error": f"Expected SELECT statement, got: {sql_query[:50]}..."}
                
                con = None
                try:
                    con = duckdb.connect()
                    con.execute(f"CREATE VIEW my_table AS SELECT * FROM '{data_path}'")
                    result_df = con.query(sql_query).pl()
                    return {
                        "sql": sql_query,
                        "columns": result_df.columns,
                        "data": result_df.head(100).to_dicts(),
                    }
                except Exception as e:
                    last_error = str(e)
                    # If it's a DuckDB error caused by bad SQL or types, trigger Auto-Correction
                    if "Conversion Error" in last_error or "Binder Error" in last_error or "Catalog Error" in last_error:
                        logger.warning("SQL crashed. Triggering Auto-Correction. Error: %s", last_error)
                        # Feed the crash log back to the LLM
                        messages.append({"role": "assistant", "content": raw_response})
                        messages.append({
                            "role": "user", 
                            "content": f"Your query crashed with this DuckDB error:\n{last_error}\n\nRewrite the query. CRITICAL: You MUST use TRY_CAST(column AS DOUBLE) when doing math/comparisons on dirty columns to avoid this exact crash."
                        })
                        continue  # Let the loop run attempt #2
                    else:
                        # Unrelated system crash
                        return {"error": f"Failed to execute. SQL: {sql_query} | Error: {last_error}"}
                finally:
                    if con:
                        con.close()

        # If it breaks out of the loop, it failed twice
        return {"error": f"AI Auto-correction failed after 2 attempts. Last Error: {last_error} | Last SQL: {sql_query}"}

    except Exception as e:
        return {"error": f"Failed to generate SQL: {str(e)}"}


def confirm_and_execute_edit(session_id: str, sql_query: str):
    session_dir = _session_dir(session_id)
    cleaned_path = f"{session_dir}/cleaned_data.parquet"
    raw_path = f"{session_dir}/raw_data.parquet"
    data_path = cleaned_path if os.path.exists(cleaned_path) else raw_path

    con = None
    try:
        con = duckdb.connect()
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
            before_count = con.execute("SELECT COUNT(*) FROM my_table").fetchone()[0]
            con.execute(clean_sql)
            after_count = con.execute("SELECT COUNT(*) FROM my_table").fetchone()[0]
            rows_affected = before_count - after_count

            con.execute(f"COPY my_table TO '{data_path}' (FORMAT PARQUET)")

            preview_df = con.query("SELECT * FROM my_table LIMIT 50").pl()
            return {
                "status": "success",
                "rows_affected": rows_affected,
                "columns": preview_df.columns,
                "preview_data": preview_df.head(50).to_dicts(),
            }

        elif upper.startswith("UPDATE"):
            try:
                if not clean_sql.upper().rstrip().endswith("RETURNING *"):
                    returning_sql = clean_sql + " RETURNING *"
                else:
                    returning_sql = clean_sql
                affected_df = con.query(returning_sql).pl()
                rows_affected = len(affected_df)
            except Exception:
                con.execute(clean_sql)
                rows_affected = 0
                affected_df = con.query("SELECT * FROM my_table LIMIT 50").pl()

            con.execute(f"COPY my_table TO '{data_path}' (FORMAT PARQUET)")
            return {
                "status": "success",
                "rows_affected": rows_affected,
                "columns": affected_df.columns,
                "preview_data": affected_df.head(50).to_dicts(),
            }
        else:
            return {"error": f"Expected UPDATE or DELETE, got: {clean_sql[:50]}"}

    except Exception as e:
        error_str = str(e)
        if "Conversion Error" in error_str:
            return {
                "error": f"Type conversion error on dirty data. Hint: The column contains mixed types (text + numbers). DuckDB: {error_str}"
            }
        return {"error": error_str}
    finally:
        if con:
            con.close()
