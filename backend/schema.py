"""
DataSentinel — Schema Enforcer
Validates uploaded datasets against minimum quality contracts.
"""

import polars as pl
import os
import json
from utils import _BACKEND_DIR, logger

class SchemaEnforcer:
    @staticmethod
    def validate(df: pl.DataFrame, dataset_name: str = None) -> dict:
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

        # SCHEMA DRIFT DETECTION
        if dataset_name:
            schema_dir = os.path.join(_BACKEND_DIR, "data", "schemas")
            os.makedirs(schema_dir, exist_ok=True)
            schema_path = os.path.join(schema_dir, f"{dataset_name}.schema.json")

            current_schema = {col: str(dtype) for col, dtype in zip(df.columns, df.dtypes)}

            if os.path.exists(schema_path):
                try:
                    with open(schema_path, "r") as f:
                        expected_schema = json.load(f)

                    drift_errors = []
                    for col, expected_type in expected_schema.items():
                        if col not in current_schema:
                            drift_errors.append(f"Missing required column: '{col}' (expected {expected_type})")
                        else:
                            expected_base = expected_type.replace('64', '').replace('32', '')
                            current_base = current_schema[col].replace('64', '').replace('32', '')
                            if expected_base != current_base:
                                drift_errors.append(f"Type drift in '{col}': expected {expected_type}, got {current_schema[col]}")

                    if drift_errors:
                        return {"valid": False, "errors": ["Schema Contract Violation:"] + drift_errors}
                except Exception as e:
                    logger.warning("Schema drift check failed (schema file may be corrupt): %s", e)
            
            # Save or update schema if no drift errors (or if it's new)
            with open(schema_path, "w") as f:
                json.dump(current_schema, f, indent=4)

        return {"valid": True, "errors": []}
