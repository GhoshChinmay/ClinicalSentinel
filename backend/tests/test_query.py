"""
DataSentinel — Query Engine Tests
Tests for SQL sanitization, TRY_CAST enforcement, and SQL injection guards.
"""

import re
import pytest

from engines.query import _sanitize_llm_sql, _force_try_cast, confirm_and_execute_edit


class TestSanitizeLLMSQL:
    """Tests for extracting clean SQL from messy LLM output."""

    def test_extracts_from_code_fence(self):
        raw = "Here's the query:\n```sql\nSELECT * FROM my_table LIMIT 10\n```\nDone!"
        result = _sanitize_llm_sql(raw)
        assert result == "SELECT * FROM my_table LIMIT 10"

    def test_extracts_from_code_fence_no_lang(self):
        raw = "```\nSELECT count(*) FROM my_table\n```"
        result = _sanitize_llm_sql(raw)
        assert result == "SELECT count(*) FROM my_table"

    def test_strips_leading_text(self):
        raw = "Sure! Here is your SQL: SELECT name FROM my_table"
        result = _sanitize_llm_sql(raw)
        assert result.startswith("SELECT")

    def test_strips_trailing_semicolon(self):
        raw = "SELECT * FROM my_table;"
        result = _sanitize_llm_sql(raw)
        assert not result.endswith(";")

    def test_handles_update(self):
        raw = "UPDATE my_table SET price = 0 WHERE id = 1"
        result = _sanitize_llm_sql(raw)
        assert result.startswith("UPDATE")

    def test_handles_delete(self):
        raw = "DELETE FROM my_table WHERE status = 'bad'"
        result = _sanitize_llm_sql(raw)
        assert result.startswith("DELETE")


class TestForceTryCast:
    """Tests for CAST → TRY_CAST replacement."""

    def test_replaces_cast(self):
        sql = "SELECT CAST(price AS DOUBLE) FROM my_table"
        result = _force_try_cast(sql)
        assert "TRY_CAST" in result
        assert "CAST(" not in result.replace("TRY_CAST", "")

    def test_does_not_double_replace(self):
        sql = "SELECT TRY_CAST(x AS INT) FROM my_table"
        result = _force_try_cast(sql)
        assert "TRY_TRY_CAST" not in result

    def test_case_insensitive(self):
        sql = "SELECT cast(amount as DOUBLE) FROM my_table"
        result = _force_try_cast(sql)
        assert "TRY_CAST(" in result


class TestSQLInjectionGuard:
    """Tests for the SQL injection prevention in confirm_and_execute_edit."""

    def test_drop_table_blocked(self, numeric_df):
        """DDL statements like DROP should be rejected."""
        from engines.detection import process_and_detect

        result = process_and_detect(df=numeric_df)
        session_id = result["session_id"]

        edit_result = confirm_and_execute_edit(session_id, "DROP TABLE my_table")
        assert "error" in edit_result
        assert "Forbidden" in edit_result["error"]

    def test_create_table_blocked(self, numeric_df):
        from engines.detection import process_and_detect

        result = process_and_detect(df=numeric_df)
        session_id = result["session_id"]

        edit_result = confirm_and_execute_edit(session_id, "CREATE TABLE evil (x INT)")
        assert "error" in edit_result

    def test_multi_statement_blocked(self, numeric_df):
        from engines.detection import process_and_detect

        result = process_and_detect(df=numeric_df)
        session_id = result["session_id"]

        # Use two UPDATE statements (both individually valid) to test the semicolon guard
        edit_result = confirm_and_execute_edit(
            session_id,
            "UPDATE my_table SET amount=1 WHERE amount > 100; UPDATE my_table SET amount=2",
        )
        assert "error" in edit_result
        assert "Multi-statement" in edit_result["error"]
