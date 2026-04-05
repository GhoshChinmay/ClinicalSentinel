"""
DataSentinel — Schema Enforcer
Validates uploaded datasets against minimum quality contracts.
"""

import polars as pl


class SchemaEnforcer:
    @staticmethod
    def validate(df: pl.DataFrame) -> dict:
        errors = []
        if len(df) == 0:
            return {"valid": False, "errors": ["The uploaded dataset is completely empty."]}

        null_counts = df.null_count().to_dict(as_series=False)
        for col, count_list in null_counts.items():
            if count_list[0] == len(df):
                errors.append(
                    f"Column '{col}' is 100% empty. Please remove ghost columns before uploading."
                )

        if len(df.columns) < 3:
            errors.append(
                f"Dataset only has {len(df.columns)} columns. A minimum of 3 columns is required for AI anomaly detection."
            )

        if errors:
            return {"valid": False, "errors": errors}

        return {"valid": True, "errors": []}
