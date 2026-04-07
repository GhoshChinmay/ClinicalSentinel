"""
DataSentinel — Detection Engine Tests
Tests for the full anomaly detection pipeline, SHAP, velocity, and NLP bridge.
"""

import polars as pl
import numpy as np
import json
import pytest

from engines.detection import process_and_detect
from engines.nlp_bridge import process_text_anomalies


class TestBasicDetection:
    """Core detection pipeline smoke tests."""

    def test_produces_required_columns(self, numeric_df):
        """Detection must produce is_anomaly, Threat_Score, AI_Reason, SHAP_Payload."""
        result = process_and_detect(df=numeric_df)
        assert result["status"] == "success"

        session_id = result["session_id"]
        from utils import _session_dir
        session_dir = _session_dir(session_id)
        df = pl.read_parquet(f"{session_dir}/raw_data.parquet")

        for col in ["is_anomaly", "Threat_Score", "AI_Reason", "SHAP_Payload"]:
            assert col in df.columns, f"Missing required column: {col}"

    def test_detects_anomalies(self, numeric_df):
        """With injected outliers, at least some anomalies should be detected."""
        result = process_and_detect(df=numeric_df)
        assert result["anomaly_count"] > 0, "Expected at least 1 anomaly from injected outliers"

    def test_total_rows_matches(self, numeric_df):
        """Total rows in result should match (after dedup) the input."""
        unique_count = len(numeric_df.unique())
        result = process_and_detect(df=numeric_df)
        assert result["total_rows"] == unique_count

    def test_deduplication(self):
        """Duplicate rows should be removed."""
        df = pl.DataFrame({
            "a": [1, 1, 2, 3, 4],
            "b": [10, 10, 20, 30, 40],
            "c": ["x", "x", "y", "z", "w"],
        })
        result = process_and_detect(df=df)
        assert result["total_rows"] == 4, "Expected 4 rows after dedup"

    def test_session_id_generated(self, numeric_df):
        """When no session_id is provided, one should be auto-generated."""
        result = process_and_detect(df=numeric_df)
        assert "session_id" in result
        assert len(result["session_id"]) == 36  # UUID format


class TestSHAPExplainability:
    """Tests for SHAP payload generation."""

    def test_shap_payloads_populated_for_anomalies(self, numeric_df):
        """Every anomaly row should have a non-empty SHAP payload."""
        result = process_and_detect(df=numeric_df)
        from utils import _session_dir
        session_dir = _session_dir(result["session_id"])
        df = pl.read_parquet(f"{session_dir}/raw_data.parquet")

        anomalies = df.filter(pl.col("is_anomaly") == True)
        if len(anomalies) > 0:
            for row in anomalies.to_dicts():
                payload = json.loads(row["SHAP_Payload"])
                assert len(payload) > 0, "Anomaly row has empty SHAP payload"
                assert "feature" in payload[0]
                assert "impact" in payload[0]


class TestVelocityEngine:
    """Tests for the time-series velocity engine."""

    def test_velocity_columns_added(self, financial_df):
        """Financial data with datetime + entity ID should trigger velocity features."""
        result = process_and_detect(df=financial_df)
        from utils import _session_dir
        session_dir = _session_dir(result["session_id"])
        df = pl.read_parquet(f"{session_dir}/raw_data.parquet")

        assert "velocity_24h_sum" in df.columns, "velocity_24h_sum not found"
        assert "velocity_1h_count" in df.columns, "velocity_1h_count not found"

    def test_velocity_skipped_without_time(self, numeric_df):
        """Without a time column, velocity columns should NOT be added."""
        result = process_and_detect(df=numeric_df)
        from utils import _session_dir
        session_dir = _session_dir(result["session_id"])
        df = pl.read_parquet(f"{session_dir}/raw_data.parquet")

        assert "velocity_24h_sum" not in df.columns
        assert "velocity_1h_count" not in df.columns


class TestNLPBridge:
    """Tests for the text feature extraction pipeline."""

    def test_structural_features_added(self, text_df):
        """Text columns should get _length, _digit_ratio, _upper_ratio, _special_ratio features."""
        result_df = process_text_anomalies(text_df)

        for suffix in ["_length", "_digit_ratio", "_upper_ratio", "_special_ratio"]:
            assert f"review{suffix}" in result_df.columns, f"Missing review{suffix}"

    def test_tfidf_pca_fires_for_large_datasets(self, text_df):
        """With >= 100 rows, TF-IDF + PCA should produce nlp_pc columns."""
        result_df = process_text_anomalies(text_df)

        assert "nlp_pc1" in result_df.columns, "Expected nlp_pc1 from TF-IDF + PCA"

    def test_tfidf_skipped_for_small_datasets(self):
        """With < 100 rows, TF-IDF should be skipped."""
        small_df = pl.DataFrame({
            "text": ["hello"] * 50,
            "value": list(range(50)),
            "cat": ["A"] * 50,
        })
        result_df = process_text_anomalies(small_df)
        assert "nlp_pc1" not in result_df.columns


class TestAIReasonGenerator:
    """Tests for AI reason generation."""

    def test_anomalies_have_reasons(self, numeric_df):
        """Every anomaly should have a non-empty AI_Reason."""
        result = process_and_detect(df=numeric_df)
        from utils import _session_dir
        session_dir = _session_dir(result["session_id"])
        df = pl.read_parquet(f"{session_dir}/raw_data.parquet")

        anomalies = df.filter(pl.col("is_anomaly") == True)
        for row in anomalies.to_dicts():
            assert row["AI_Reason"] != "", f"Anomaly at row has empty AI_Reason"

    def test_reasons_are_dynamic_not_identical(self, numeric_df):
        """AI reasons should be dynamic per-row, not the same generic text for every anomaly."""
        result = process_and_detect(df=numeric_df)
        from utils import _session_dir
        session_dir = _session_dir(result["session_id"])
        df = pl.read_parquet(f"{session_dir}/raw_data.parquet")

        anomalies = df.filter(pl.col("is_anomaly") == True)
        reasons = [r["AI_Reason"] for r in anomalies.to_dicts()]

        if len(reasons) > 1:
            # Not ALL reasons should be identical — at least some should differ
            unique_reasons = set(reasons)
            assert len(unique_reasons) > 1, (
                f"All {len(reasons)} anomalies have the identical reason: '{reasons[0]}'. "
                "Reasons should be dynamic and vary by row."
            )

    def test_reasons_contain_actual_values(self, numeric_df):
        """AI reasons should reference actual column values for specificity."""
        result = process_and_detect(df=numeric_df)
        from utils import _session_dir
        session_dir = _session_dir(result["session_id"])
        df = pl.read_parquet(f"{session_dir}/raw_data.parquet")

        anomalies = df.filter(pl.col("is_anomaly") == True)
        reasons = [r["AI_Reason"] for r in anomalies.to_dicts()]

        # At least some reasons should contain numeric values (actual data points)
        has_numbers = sum(1 for r in reasons if any(c.isdigit() for c in r))
        assert has_numbers > 0, "No reasons contain actual numeric values — they should be data-specific"


class TestCleaningRecommendation:
    """Tests for the smart cleaning recommendation engine."""

    def test_financial_data_recommends_quarantine(self, financial_df):
        """Financial datasets should recommend quarantine."""
        result = process_and_detect(df=financial_df)
        assert result["recommended_cleaning"] == "quarantine"

    def test_text_data_recommends_mask(self, text_df):
        """Text-heavy datasets should recommend mask."""
        result = process_and_detect(df=text_df)
        assert result["recommended_cleaning"] == "mask"
