"""
DataSentinel — Insights Engine Tests
Tests for generating insights without OIA framework and fallback mechanisms.
"""

import pytest
from unittest.mock import patch

from engines.insights import generate_insights


class TestGenerateInsightsFallback:
    """Tests for fallback behavior when Groq is unavailable."""

    def test_fallback_on_api_error(self, numeric_df):
        """When Groq API fails, generate_insights should provide a fallback AI narrative."""
        from engines.detection import process_and_detect

        result = process_and_detect(df=numeric_df)
        session_id = result["session_id"]

        # Mock groq API to raise an Exception
        with patch("groq_client.groq_chat_json") as mock_groq:
            mock_groq.side_effect = Exception("Groq API not reachable")
            insights_result = generate_insights(session_id)

        assert "summary" in insights_result
        assert "executive_summary" in insights_result["summary"]
        assert "key_findings" in insights_result["summary"]
        assert isinstance(insights_result["summary"]["key_findings"], list)
