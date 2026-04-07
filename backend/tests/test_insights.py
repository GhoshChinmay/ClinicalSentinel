"""
DataSentinel — Insights Engine Tests
Tests for fuzzy key matching, OIA extraction, and connection error fallback.
"""

import pytest
from unittest.mock import patch

from engines.insights import (
    _fuzzy_get,
    _extract_oia_insights,
    _is_oia_like,
    generate_insights,
    _OBSERVATION_KEYS,
    _INSIGHT_KEYS,
    _ACTION_KEYS,
)


class TestFuzzyGet:
    """Tests for flexible key matching across LLM response variants."""

    def test_exact_match(self):
        obj = {"observation": "Something happened", "insight": "It matters"}
        assert _fuzzy_get(obj, _OBSERVATION_KEYS) == "Something happened"

    def test_alias_match(self):
        obj = {"finding": "Data drift", "interpretation": "Significant shift"}
        assert _fuzzy_get(obj, _OBSERVATION_KEYS) == "Data drift"
        assert _fuzzy_get(obj, _INSIGHT_KEYS) == "Significant shift"

    def test_partial_match(self):
        obj = {"recommended_action": "Fix it now", "other_key": "ignored"}
        assert _fuzzy_get(obj, _ACTION_KEYS) == "Fix it now"

    def test_returns_empty_for_no_match(self):
        obj = {"unrelated_key": "value"}
        assert _fuzzy_get(obj, _OBSERVATION_KEYS) == ""

    def test_skips_list_values(self):
        """fuzzy_get should skip list values and return empty."""
        obj = {"observation": ["item1", "item2"]}
        assert _fuzzy_get(obj, _OBSERVATION_KEYS) == ""

    def test_skips_none_values(self):
        obj = {"observation": None, "finding": "Actual finding"}
        assert _fuzzy_get(obj, _OBSERVATION_KEYS) == "Actual finding"


class TestIsOIALike:
    """Tests for recognizing OIA-structured dictionaries."""

    def test_detects_observation_key(self):
        assert _is_oia_like(["observation", "insight", "action"])

    def test_detects_aliased_keys(self):
        assert _is_oia_like(["finding", "analysis", "recommendation"])

    def test_rejects_unrelated_keys(self):
        assert not _is_oia_like(["name", "age", "score"])


class TestExtractOIAInsights:
    """Tests for the recursive OIA insight extractor."""

    def test_flat_array(self):
        data = [
            {"observation": "Obs1", "insight": "Ins1", "action": "Act1"},
            {"observation": "Obs2", "insight": "Ins2", "action": "Act2"},
        ]
        results = _extract_oia_insights(data)
        assert len(results) == 2
        assert results[0]["observation"] == "Obs1"

    def test_nested_wrapper(self):
        data = {"insights": [
            {"observation": "Obs1", "insight": "Ins1", "action": "Act1"},
        ]}
        results = _extract_oia_insights(data)
        assert len(results) >= 1

    def test_deeply_nested(self):
        data = {"data": {"results": [
            {"finding": "Deep finding", "analysis": "Deep analysis", "suggestion": "Do this"},
        ]}}
        results = _extract_oia_insights(data)
        assert len(results) >= 1
        assert results[0]["observation"] == "Deep finding"

    def test_handles_empty_input(self):
        assert _extract_oia_insights([]) == []
        assert _extract_oia_insights({}) == []

    def test_handles_string_input(self):
        """Edge case: raw string passed (not a dict/list)."""
        assert _extract_oia_insights("just a string") == []


class TestGenerateInsightsFallback:
    """Tests for fallback behavior when Ollama is unavailable."""

    def test_fallback_on_connection_error(self, numeric_df):
        """When Ollama is down, generate_insights should return 3 valid fallback insights."""
        from engines.detection import process_and_detect
        result = process_and_detect(df=numeric_df)
        session_id = result["session_id"]

        # Mock requests.post to raise ConnectionError
        with patch("engines.insights.requests.post") as mock_post:
            mock_post.side_effect = ConnectionError("Ollama not running")
            insights_result = generate_insights(session_id)

        assert "insights" in insights_result
        assert len(insights_result["insights"]) == 3

        for insight in insights_result["insights"]:
            assert "observation" in insight
            assert "insight" in insight
            assert "action" in insight
            assert len(insight["observation"]) > 0
