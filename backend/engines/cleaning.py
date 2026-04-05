"""
DataSentinel — Cleaning Engine
Five sanitization strategies: Quarantine, Winsorize, Mask, Impute, Drop.
"""

import os
import polars as pl
import numpy as np
import pandas as pd
from sklearn.impute import KNNImputer

from utils import _session_dir, logger


def clean_dataset(session_id: str, action: str = "drop"):
    session_dir = _session_dir(session_id)
    raw_parquet_path = f"{session_dir}/raw_data.parquet"

    if not os.path.exists(raw_parquet_path):
        return {"error": "Dataset not found."}

    df = pl.read_parquet(raw_parquet_path)
    original_count = len(df)

    if action in ["drop", "quarantine"]:
        quarantined_df = df.filter(pl.col("is_anomaly") == True)
        if len(quarantined_df) > 0:
            quarantined_df.write_parquet(f"{session_dir}/quarantined_data.parquet")

        cleaned_df = df.filter(pl.col("is_anomaly") == False)

    elif action == "winsorize":
        numeric_cols = [
            col for col, dtype in zip(df.columns, df.dtypes)
            if dtype in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]
        ]
        normal_data = df.filter(pl.col("is_anomaly") == False)

        exprs = []
        for col in numeric_cols:
            if col in ["is_anomaly", "Threat_Score"]:
                continue

            lower_bound = normal_data[col].quantile(0.05)
            upper_bound = normal_data[col].quantile(0.95)

            if lower_bound is None or upper_bound is None:
                logger.info("[WINSORIZE] Skipping '%s' — all-null column.", col)
                continue

            expr = (
                pl.when(pl.col("is_anomaly") == True)
                .then(pl.col(col).clip(lower_bound, upper_bound))
                .otherwise(pl.col(col))
                .alias(col)
            )
            exprs.append(expr)

        cleaned_df = df.with_columns(exprs)

    elif action == "mask":
        string_cols = [
            col for col, dtype in zip(df.columns, df.dtypes)
            if dtype in [pl.Utf8, getattr(pl, "String", pl.Utf8)]
        ]

        safe_text_cols = []
        for col in string_cols:
            if col in ["AI_Reason", "is_anomaly", "Threat_Score"]:
                continue
            try:
                sample = df[col].drop_nulls()
                if len(sample) == 0:
                    continue
                stripped = sample.str.replace_all(r"[₹$€£¥,\s]", "").str.strip_chars()
                numeric_count = stripped.str.contains(r"^-?\d+\.?\d*$").sum()
                numeric_ratio = numeric_count / len(sample)
                if numeric_ratio > 0.5:
                    logger.info("[MASK SAFEGUARD] Skipping column '%s' — %.0f%% numeric content detected.", col, numeric_ratio * 100)
                    continue
                safe_text_cols.append(col)
            except Exception:
                safe_text_cols.append(col)

        if not safe_text_cols:
            logger.info("[MASK SAFEGUARD] No safe text columns found. Falling back to quarantine.")
            quarantined_df = df.filter(pl.col("is_anomaly") == True)
            if len(quarantined_df) > 0:
                quarantined_df.write_parquet(f"{session_dir}/quarantined_data.parquet")
            cleaned_df = df.filter(pl.col("is_anomaly") == False)
        else:
            exprs = []
            for col in safe_text_cols:
                expr = (
                    pl.when(pl.col("is_anomaly") == True)
                    .then(pl.lit("[REDACTED_ANOMALY]"))
                    .otherwise(pl.col(col))
                    .alias(col)
                )
                exprs.append(expr)
            cleaned_df = df.with_columns(exprs)

    elif action == "impute":
        numeric_cols = [
            col for col, dtype in zip(df.columns, df.dtypes)
            if dtype in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]
        ]

        target_cols = [c for c in numeric_cols if c not in ["is_anomaly", "Threat_Score"] and not c.endswith("_freq")]

        if target_cols:
            logger.info("Running K-Nearest Neighbors Predictive Imputation...")

            pandas_df = df.to_pandas()

            for col in target_cols:
                pandas_df.loc[pandas_df["is_anomaly"] == True, col] = np.nan

            imputer = KNNImputer(n_neighbors=5, weights="distance")
            pandas_df[target_cols] = imputer.fit_transform(pandas_df[target_cols])

            for col in target_cols:
                df = df.with_columns(pl.Series(name=col, values=pandas_df[col]))

        cleaned_df = df

    else:
        return {"error": f"Unknown cleaning action: {action}"}

    # Strip ALL engineered columns from the final output
    engineered_suffixes = ("_freq", "_length", "_digit_ratio", "_upper_ratio", "_special_ratio")
    engineered_prefixes = ("nlp_pc",)
    velocity_names = {"velocity_24h_sum", "velocity_1h_count"}
    always_drop = {"is_anomaly", "AI_Reason", "Threat_Score"}

    cols_to_drop = [
        c for c in cleaned_df.columns
        if c in always_drop
        or c.endswith(engineered_suffixes)
        or any(c.startswith(p) for p in engineered_prefixes)
        or c in velocity_names
    ]
    cleaned_df = cleaned_df.drop([c for c in cols_to_drop if c in cleaned_df.columns])

    cleaned_parquet_path = f"{session_dir}/cleaned_data.parquet"
    cleaned_df.write_parquet(cleaned_parquet_path)

    return {
        "status": "success",
        "action_taken": action,
        "original_rows": original_count,
        "new_total": len(cleaned_df),
    }
