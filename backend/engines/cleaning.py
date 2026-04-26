"""
DataSentinel — Cleaning Engine (Godmode Edition)
Five sanitization strategies: Quarantine, Winsorize, Mask, Impute, Drop.
"""

import os
import polars as pl
import numpy as np
import pandas as pd

from utils import _session_dir, logger


def clean_dataset(session_id: str, action: str = "drop"):
    """
    Applies enterprise-grade data cleaning mutations and saves to cleaned_data.parquet.
    """
    session_dir = _session_dir(session_id)
    raw_parquet_path = f"{session_dir}/raw_data.parquet"

    if not os.path.exists(raw_parquet_path):
        return {"error": "Dataset not found."}

    df = pl.read_parquet(raw_parquet_path)
    original_count = len(df)
    cleaned_df = df # Default fallback

    try:
        # ── ACTION: DROP / QUARANTINE ──
        if action in ["drop", "quarantine"]:
            if "is_anomaly" in df.columns:
                quarantined_df = df.filter(pl.col("is_anomaly") == True)
                if len(quarantined_df) > 0:
                    quarantined_df.write_parquet(f"{session_dir}/quarantined_data.parquet")
                cleaned_df = df.filter(pl.col("is_anomaly") == False)
            else:
                cleaned_df = df.drop_nulls()

        # ── ACTION: WINSORIZE (Clipping Outliers) ──
        elif action == "winsorize":
            numeric_cols = [c for c, dtype in zip(df.columns, df.dtypes) if dtype in pl.NUMERIC_DTYPES]
            normal_data = df.filter(pl.col("is_anomaly") == False) if "is_anomaly" in df.columns else df

            exprs = []
            for col in numeric_cols:
                if col in ["is_anomaly", "Threat_Score"]:
                    continue

                lower_bound = normal_data[col].quantile(0.05)
                upper_bound = normal_data[col].quantile(0.95)

                if lower_bound is None or upper_bound is None:
                    continue

                if "is_anomaly" in df.columns:
                    expr = (
                        pl.when(pl.col("is_anomaly") == True)
                        .then(pl.col(col).clip(lower_bound, upper_bound))
                        .otherwise(pl.col(col))
                        .alias(col)
                    )
                else:
                    expr = pl.col(col).clip(lower_bound, upper_bound).alias(col)
                exprs.append(expr)

            cleaned_df = df.with_columns(exprs)

        # ── ACTION: MASK (Redacting Strings) ──
        elif action == "mask":
            string_cols = [c for c, dtype in zip(df.columns, df.dtypes) if dtype in [pl.Utf8, getattr(pl, "String", pl.Utf8)]]
            safe_text_cols = []
            
            for col in string_cols:
                if col in ["AI_Reason", "is_anomaly", "Threat_Score", "SHAP_Payload"]:
                    continue
                try:
                    sample = df[col].drop_nulls()
                    if len(sample) == 0:
                        continue
                    stripped = sample.str.replace_all(r"[₹$€£¥,\s]", "").str.strip_chars()
                    numeric_ratio = stripped.str.contains(r"^-?\d+\.?\d*$").sum() / len(sample)
                    if numeric_ratio > 0.5:
                        continue # Skip numeric-like strings
                    safe_text_cols.append(col)
                except Exception:
                    safe_text_cols.append(col)

            if safe_text_cols and "is_anomaly" in df.columns:
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
            else:
                cleaned_df = df

        # ── ACTION: MEDIAN FALLBACK ──
        elif action == "median":
            numeric_cols = [c for c, dtype in zip(df.columns, df.dtypes) if dtype in pl.NUMERIC_DTYPES]
            for col in numeric_cols:
                cleaned_df = cleaned_df.with_columns(pl.col(col).fill_null(pl.median(col)))

        # ── ACTION: GODMODE KNN IMPUTATION ──
        elif action == "impute":
            logger.info("Initiating Godmode KNN Imputation...")
            try:
                from sklearn.impute import KNNImputer
                from sklearn.preprocessing import StandardScaler
            except ImportError:
                return {"error": "scikit-learn is required. Run: pip install scikit-learn pandas"}

            # 1. Isolate only mathematically valid numeric columns
            # Exclude internal/engineered suffixes so we only impute user-owned data.
            _IMPUTE_EXCLUDE_COLS = {
                "is_anomaly", "Threat_Score", "lof_score", "ecod_score",
                "lstm_anomaly_score", "logic_violation",
            }
            _IMPUTE_EXCLUDE_SUFFIXES = (
                "_freq", "_length", "_digit_ratio", "_upper_ratio",
                "_special_ratio", "_entity_z",
            )
            _IMPUTE_EXCLUDE_PREFIXES = ("nlp_pc", "Score_CI", "velocity_")

            numeric_cols = [
                col for col, dtype in zip(df.columns, df.dtypes)
                if dtype in pl.NUMERIC_DTYPES
                and col not in _IMPUTE_EXCLUDE_COLS
                and not any(col.endswith(s) for s in _IMPUTE_EXCLUDE_SUFFIXES)
                and not any(col.startswith(p) for p in _IMPUTE_EXCLUDE_PREFIXES)
            ]

            if not numeric_cols:
                return {"error": "No continuous numeric columns found for KNN math."}

            pandas_df = df.to_pandas()

            # 2. If anomalies exist, punch them out (set to NaN) so KNN can overwrite them
            if "is_anomaly" in pandas_df.columns:
                anomaly_mask = pandas_df["is_anomaly"].astype(bool) == True
                pandas_df.loc[anomaly_mask, numeric_cols] = np.nan

            numeric_df = pandas_df[numeric_cols]

            # Guard: if ALL values are NaN (i.e., 100% anomaly rate), KNN has nothing
            # to impute from. Return the original data gracefully instead of crashing.
            if numeric_df.isna().all().all():
                logger.warning(
                    "KNN Impute aborted: all numeric columns are fully NaN (100%% anomaly rate). "
                    "Returning original data unchanged."
                )
                cleaned_df = df
                cleaned_df.write_parquet(f"{session_dir}/cleaned_data.parquet")
                return {
                    "status": "success",
                    "action_taken": action,
                    "original_rows": original_count,
                    "new_total": len(cleaned_df),
                    "warning": "KNN imputation skipped — all rows were anomalous (no clean anchor rows).",
                }

            # 3. Godmode Scaling: Prevents large numbers (Fare) from overpowering small numbers (Age)
            scaler = StandardScaler()
            scaled_array = scaler.fit_transform(numeric_df)

            # Secondary guard: scaler may drop all-constant/NaN columns → shape (N, 0).
            if scaled_array.shape[1] == 0:
                logger.warning("KNN Impute aborted: StandardScaler produced 0 features.")
                cleaned_df = df
                cleaned_df.write_parquet(f"{session_dir}/cleaned_data.parquet")
                return {
                    "status": "success",
                    "action_taken": action,
                    "original_rows": original_count,
                    "new_total": len(cleaned_df),
                    "warning": "KNN imputation skipped — no valid numeric features after scaling.",
                }

            # 4. K-Nearest Neighbors Imputation
            imputer = KNNImputer(n_neighbors=5, weights="distance")
            imputed_scaled = imputer.fit_transform(scaled_array)

            # 5. Inverse Scale back to real-world numbers
            imputed_array = scaler.inverse_transform(imputed_scaled)

            # 6. Stitch back into Polars DataFrame securely
            imputed_pl = pl.from_pandas(pd.DataFrame(imputed_array, columns=numeric_cols))

            for col in numeric_cols:
                # Force the new imputed data to strictly match the original Polars datatype
                df = df.with_columns(imputed_pl[col].cast(df[col].dtype, strict=False))

            cleaned_df = df

        else:
            return {"error": f"Unknown cleaning action: {action}"}

        # ── FINAL STRIP & EXPORT ──
        engineered_suffixes = ("_freq", "_length", "_digit_ratio", "_upper_ratio", "_special_ratio")
        engineered_prefixes = ("nlp_pc",)
        velocity_names = {"velocity_24h_sum", "velocity_1h_count"}
        
        # FIX: Expanded Wipe List to include ALL new Godmode features
        always_drop = {
            "is_anomaly", "AI_Reason", "Threat_Score", "SHAP_Payload", 
            "Counterfactual_Payload", "lof_score", "ecod_score", "lstm_anomaly_score"
        }

        cols_to_drop = [
            c for c in cleaned_df.columns
            if c in always_drop
            or c.startswith("Score_CI") # Catches hidden Scikit-Learn/PyOD confidence intervals
            or c.endswith(engineered_suffixes)
            or any(c.startswith(p) for p in engineered_prefixes)
            or c in velocity_names
        ]
        cleaned_df = cleaned_df.drop([c for c in cols_to_drop if c in cleaned_df.columns])

        # ── GDPR PII SCRUBBER ──
        try:
            string_cols = [c for c, dtype in zip(cleaned_df.columns, cleaned_df.dtypes) if dtype in [pl.Utf8, getattr(pl, "String", pl.Utf8)]]
            pii_exprs = []
            for col in string_cols:
                expr = (
                    pl.col(col)
                    .str.replace_all(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[REDACTED_EMAIL]")
                    .str.replace_all(r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]")
                    .str.replace_all(r"\b(?:\d[ -]*?){13,16}\b", "[REDACTED_CC]")
                    .alias(col)
                )
                pii_exprs.append(expr)

            if pii_exprs:
                cleaned_df = cleaned_df.with_columns(pii_exprs)
        except Exception as e:
            logger.warning("Failed to run PII scrubber: %s", e)

        # Write the final pristine dataset
        cleaned_df.write_parquet(f"{session_dir}/cleaned_data.parquet")

        return {
            "status": "success",
            "action_taken": action,
            "original_rows": original_count,
            "new_total": len(cleaned_df),
        }

    except Exception as e:
        logger.error("Cleaning Action '%s' failed: %s", action, e)
        return {"error": f"Data cleaning failed: {str(e)}"}