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

        assert "ai_narrative" in insights_result
        assert isinstance(insights_result["ai_narrative"], list)
        assert len(insights_result["ai_narrative"]) >= 1

        for sentence in insights_result["ai_narrative"]:
            assert isinstance(sentence, str)
            assert len(sentence) > 0
