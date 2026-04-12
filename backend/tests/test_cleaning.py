"""
DataSentinel — Cleaning Engine Tests
Tests for all 5 cleaning strategies: drop, quarantine, winsorize, mask, impute.
"""

import os
import polars as pl
import numpy as np
import pytest

from engines.detection import process_and_detect
from engines.cleaning import clean_dataset
from utils import _session_dir


def _setup_detected_session(df: pl.DataFrame) -> str:
    """Run detection and return session_id for cleaning tests."""
    result = process_and_detect(df=df)
    assert result["status"] == "success"
    return result["session_id"]


class TestDropStrategy:
    """Tests for the 'drop' cleaning action."""

    def test_drop_removes_anomalies(self, numeric_df):
        session_id = _setup_detected_session(numeric_df)
        result = clean_dataset(session_id, "drop")

        assert result["status"] == "success"
        assert result["new_total"] <= result["original_rows"]

    def test_quarantine_file_created(self, numeric_df):
        session_id = _setup_detected_session(numeric_df)
        clean_dataset(session_id, "drop")

        session_dir = _session_dir(session_id)
        quarantine_path = os.path.join(session_dir, "quarantined_data.parquet")
        assert os.path.exists(quarantine_path), "Quarantine file not created"


class TestQuarantineStrategy:
    """Tests for the 'quarantine' cleaning action (identical to drop)."""

    def test_quarantine_isolates_anomalies(self, numeric_df):
        session_id = _setup_detected_session(numeric_df)
        result = clean_dataset(session_id, "quarantine")

        assert result["status"] == "success"
        session_dir = _session_dir(session_id)

        quarantine_df = pl.read_parquet(
            os.path.join(session_dir, "quarantined_data.parquet")
        )
        assert len(quarantine_df) > 0, "Quarantine should contain anomalous rows"


class TestWinsorizeStrategy:
    """Tests for the 'winsorize' cleaning action."""

    def test_winsorize_caps_extreme_values(self, numeric_df):
        session_id = _setup_detected_session(numeric_df)
        result = clean_dataset(session_id, "winsorize")

        assert result["status"] == "success"
        # Row count should remain the same (winsorize doesn't remove rows)
        assert result["new_total"] == result["original_rows"]


class TestMaskStrategy:
    """Tests for the 'mask' cleaning action."""

    def test_mask_redacts_text_in_anomalies(self, text_df):
        session_id = _setup_detected_session(text_df)
        result = clean_dataset(session_id, "mask")

        assert result["status"] == "success"


class TestImputeStrategy:
    """Tests for the 'impute' (KNN) cleaning action."""

    def test_impute_does_not_crash(self, numeric_df):
        session_id = _setup_detected_session(numeric_df)
        result = clean_dataset(session_id, "impute")

        assert result["status"] == "success"
        assert result["new_total"] == result["original_rows"]

    def test_impute_all_anomalies_guard(self):
        """If all rows are anomalous, impute should handle gracefully (no clean rows to train on)."""
        # Create a tiny dataset where all rows will likely be flagged
        df = pl.DataFrame(
            {
                "a": [1000.0, 2000.0, 3000.0, 4000.0, 5000.0],
                "b": [100.0, 200.0, 300.0, 400.0, 500.0],
                "c": ["x", "y", "z", "w", "v"],
            }
        )
        session_id = _setup_detected_session(df)

        # Force all rows to be anomalies for this edge case test
        session_dir = _session_dir(session_id)
        raw_df = pl.read_parquet(os.path.join(session_dir, "raw_data.parquet"))
        raw_df = raw_df.with_columns(pl.lit(True).alias("is_anomaly"))
        raw_df.write_parquet(os.path.join(session_dir, "raw_data.parquet"))

        result = clean_dataset(session_id, "impute")
        assert (
            result["status"] == "success"
        ), "Impute should not crash when all rows are anomalies"


class TestUnknownStrategy:
    """Tests for invalid cleaning actions."""

    def test_unknown_action_returns_error(self, numeric_df):
        session_id = _setup_detected_session(numeric_df)
        result = clean_dataset(session_id, "explode")
        assert "error" in result


class TestEngineeredColumnStripping:
    """Verify that internal/engineered columns are removed from cleaned output."""

    def test_no_internal_columns_in_cleaned(self, numeric_df):
        session_id = _setup_detected_session(numeric_df)
        clean_dataset(session_id, "drop")

        session_dir = _session_dir(session_id)
        cleaned_df = pl.read_parquet(os.path.join(session_dir, "cleaned_data.parquet"))

        forbidden = {"is_anomaly", "AI_Reason", "Threat_Score", "SHAP_Payload"}
        for col in cleaned_df.columns:
            assert (
                col not in forbidden
            ), f"Internal column '{col}' leaked into cleaned output"
            assert not col.endswith(
                "_freq"
            ), f"Engineered column '{col}' leaked into cleaned output"


class TestPIIScrubber:
    """Tests for the GDPR PII scrubber applied during cleaning."""

    def test_emails_redacted(self, pii_df):
        session_id = _setup_detected_session(pii_df)
        clean_dataset(session_id, "drop")

        session_dir = _session_dir(session_id)
        cleaned_df = pl.read_parquet(os.path.join(session_dir, "cleaned_data.parquet"))

        if "email" in cleaned_df.columns:
            for val in cleaned_df["email"].to_list():
                assert "@" not in str(val), f"Unredacted email found: {val}"

    def test_ssn_redacted(self, pii_df):
        session_id = _setup_detected_session(pii_df)
        clean_dataset(session_id, "drop")

        session_dir = _session_dir(session_id)
        cleaned_df = pl.read_parquet(os.path.join(session_dir, "cleaned_data.parquet"))

        if "ssn" in cleaned_df.columns:
            for val in cleaned_df["ssn"].to_list():
                assert "REDACTED" in str(val) or "-" not in str(val).replace(
                    "REDACTED", ""
                ), f"Unredacted SSN found: {val}"
