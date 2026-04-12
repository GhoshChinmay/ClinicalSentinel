"""
DataSentinel — Schema Enforcer Tests
Tests for dataset validation contracts.
"""

import polars as pl
import pytest

from schema import SchemaEnforcer


class TestSchemaValidation:
    """Tests for the SchemaEnforcer.validate method."""

    def test_empty_dataset_rejected(self):
        df = pl.DataFrame({"a": [], "b": [], "c": []}).cast(
            {"a": pl.Int64, "b": pl.Int64, "c": pl.Int64}
        )
        result = SchemaEnforcer.validate(df)
        assert not result["valid"]
        assert any("empty" in e.lower() for e in result["errors"])

    def test_ghost_columns_rejected(self):
        """Columns with 100% null values should be rejected."""
        df = pl.DataFrame(
            {
                "name": ["Alice", "Bob", "Charlie"],
                "ghost": [None, None, None],
                "value": [1, 2, 3],
            }
        )
        result = SchemaEnforcer.validate(df)
        assert not result["valid"]
        assert any("ghost" in e.lower() for e in result["errors"])

    def test_minimum_columns_enforced(self):
        """Datasets with fewer than 3 columns should be rejected."""
        df = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        result = SchemaEnforcer.validate(df)
        assert not result["valid"]
        assert any("3 columns" in e for e in result["errors"])

    def test_valid_dataset_passes(self, numeric_df):
        """A clean dataset should pass validation."""
        result = SchemaEnforcer.validate(numeric_df)
        assert result["valid"]
        assert len(result["errors"]) == 0

    def test_mixed_valid_dataset(self):
        """A dataset with mixed types but valid structure should pass."""
        df = pl.DataFrame(
            {
                "name": ["Alice", "Bob", "Charlie"],
                "age": [25, 30, 35],
                "score": [0.9, 0.85, 0.78],
            }
        )
        result = SchemaEnforcer.validate(df)
        assert result["valid"]
