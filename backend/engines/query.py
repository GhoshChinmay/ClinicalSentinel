"""
DataSentinel — Natural Language Query Engine
Translates English to SQL via Ollama/Llama3 and executes against DuckDB.
"""

import os
import re
import polars as pl
import ollama
import duckdb

from utils import _session_dir, logger


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
                        stripped = sample.str.replace_all(r"[₹$€£¥,%\s]", "").str.strip_chars()
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
1. NEVER use CAST(). ALWAYS use TRY_CAST() instead. This prevents crashes on mixed-type columns.
2. For string columns that contain numeric-like data (prices, ratings), use TRY_CAST(column AS DOUBLE) to safely convert.
3. When filtering on numeric conditions for string columns, use: TRY_CAST(column AS DOUBLE) IS NOT NULL AND TRY_CAST(column AS DOUBLE) < value
4. Handle NULL values gracefully — never assume a column is clean.
5. Use LIMIT 100 for SELECT queries unless the user explicitly asks for all results.
"""

        if is_edit:
            system_prompt += "\nReturn ONLY a valid SQL UPDATE or DELETE statement. You are a machine. Do NOT output conversational text like 'Here is the query'. Start your response strictly with the word UPDATE or DELETE. Do NOT include a trailing semicolon."
        else:
            system_prompt += "\nReturn ONLY a valid SQL SELECT statement. You are a machine. Do NOT output conversational text. Start your response strictly with the word SELECT. Do NOT include a trailing semicolon."

        response = ollama.chat(model="llama3:latest", messages=[{"role": "system", "content": system_prompt}])
        # H-04 FIX: ollama ≥0.2.0 returns a Pydantic ChatResponse object, NOT a dict.
        # Use attribute access (.message.content) to be compatible with both old and new versions.
        raw_response_obj = response["message"]["content"] if isinstance(response, dict) else response.message.content
        raw_response = raw_response_obj.strip()

        sql_query = _sanitize_llm_sql(raw_response)
        sql_query = _force_try_cast(sql_query)

        logger.info("SQL: %s", sql_query)

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
                return {"sql": sql_query, "columns": result_df.columns, "data": result_df.head(100).to_dicts()}
            except Exception as e:
                error_str = str(e)
                if "Conversion Error" in error_str:
                    return {"error": f"Type conversion error — a column contains mixed data types. SQL: {sql_query} | Hint: Use TRY_CAST instead of CAST. | DuckDB: {error_str}"}
                return {"error": f"Failed to execute. SQL: {sql_query} | Error: {error_str}"}
            finally:
                if con:
                    con.close()
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
            re.IGNORECASE
        )
        if _FORBIDDEN_PATTERNS.search(clean_sql):
            return {"error": "Forbidden SQL statement type. Only UPDATE and DELETE are permitted."}
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
            return {"error": f"Type conversion error on dirty data. Hint: The column contains mixed types (text + numbers). DuckDB: {error_str}"}
        return {"error": error_str}
    finally:
        if con:
            con.close()
