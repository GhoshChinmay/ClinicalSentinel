"""
DataSentinel — Visualization Engine
Distribution histograms, correlation matrices, categorical frequency, and health scoring.
"""

import os
import polars as pl
import numpy as np

from utils import _session_dir, logger


def _compute_health_score(df_raw: pl.DataFrame, df_clean: pl.DataFrame = None) -> int:
    """Compute a real data health score based on anomaly rate and null density."""
    total = len(df_raw)
    total_cells = total * len(df_raw.columns)
    score = 100.0

    # Penalty: anomaly rate (up to -35 points)
    if "is_anomaly" in df_raw.columns and total > 0:
        anomaly_count = df_raw.filter(pl.col("is_anomaly") == True).height
        anomaly_pct = anomaly_count / total
        score -= anomaly_pct * 35

    # Penalty: null density (up to -25 points)
    if total_cells > 0:
        null_total = sum(df_raw[c].null_count() for c in df_raw.columns)
        null_pct = null_total / total_cells
        score -= null_pct * 25

    # Bonus: cleaning applied (+15 points, capped at 100)
    if df_clean is not None:
        score += 15

    return max(0, min(100, round(score)))


def get_global_histogram(df, numeric_cols):
    if df is None or len(df) == 0 or not numeric_cols:
        return []

    try:
        exprs = [
            ((pl.col(c) - pl.col(c).mean()) / (pl.col(c).std() + 1e-9)).alias(c)
            for c in numeric_cols
        ]
        normalized_df = df.select(exprs)

        try:
            flat_series = normalized_df.unpivot().drop_nulls().get_column("value")
        except AttributeError:
            flat_series = normalized_df.melt().drop_nulls().get_column("value")

        flat_values = flat_series.to_numpy()
        hist, bins = np.histogram(flat_values, bins=30, range=(-5, 5))

        return [{"bin": f"{bins[i]:.1f}σ", "count": int(hist[i])} for i in range(len(hist))]
    except Exception as e:
        logger.warning("Histogram Generation Failed: %s", e)
        return []


def get_viz_data(session_id: str):
    session_dir = _session_dir(session_id)
    raw_path = f"{session_dir}/raw_data.parquet"
    clean_path = f"{session_dir}/cleaned_data.parquet"

    if not os.path.exists(raw_path):
        return {"error": "Data not found"}

    df_raw = pl.read_parquet(raw_path)
    df_clean = pl.read_parquet(clean_path) if os.path.exists(clean_path) else None

    # BUG-11 FIX: Added SHAP_Payload which was leaking into histograms/correlation
    internal_cols = ["is_anomaly", "Threat_Score", "Class", "AI_Reason", "SHAP_Payload"]
    engineered_suffixes = ("_freq", "_length", "_digit_ratio", "_upper_ratio", "_special_ratio")
    engineered_prefixes = ("nlp_pc",)
    velocity_names = {"velocity_24h_sum", "velocity_1h_count"}

    numeric_cols = []
    categorical_cols = []

    for c, d in zip(df_raw.columns, df_raw.dtypes):
        if c in internal_cols or c in velocity_names:
            continue
        if c.endswith(engineered_suffixes) or any(c.startswith(p) for p in engineered_prefixes):
            continue
        if df_clean is not None and c not in df_clean.columns:
            continue

        if "Int" in str(d) or "Float" in str(d):
            numeric_cols.append(c)
        elif "String" in str(d) or "Utf8" in str(d) or "Object" in str(d):
            categorical_cols.append(c)

    # Correlation matrix
    correlation_data = None
    if len(numeric_cols) > 1:
        try:
            df_for_corr = df_clean if df_clean is not None else df_raw
            corr_df = df_for_corr.select(numeric_cols).to_pandas().corr().fillna(0)
            correlation_data = {"features": numeric_cols, "matrix": corr_df.values.tolist()}
        except Exception as e:
            logger.warning("Correlation matrix failed: %s", e)

    # Categorical frequency
    cat_data = []
    df_target = df_clean if df_clean is not None else df_raw
    for col in categorical_cols:
        try:
            vc = df_target.get_column(col).value_counts().sort("count", descending=True).head(10)

            val_col = vc.columns[0]
            count_col = next((c for c in vc.columns if c == "count"), vc.columns[1])

            items = [
                {
                    "label": str(row[val_col])[:35] + ("..." if len(str(row[val_col])) > 35 else ""),
                    "count": row[count_col],
                }
                for row in vc.to_dicts()
            ]
            cat_data.append({"column": col, "top_values": items})
        except Exception as e:
            logger.warning("Category data failed for '%s': %s", col, e)

    # Compute real health score
    health_score = _compute_health_score(df_raw, df_clean)

    return {
        "columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "global_raw_hist": get_global_histogram(df_raw, numeric_cols) if numeric_cols else [],
        "global_clean_hist": get_global_histogram(df_clean, numeric_cols) if df_clean is not None and numeric_cols else [],
        "clean_sample": df_clean.head(1000).to_dicts() if df_clean is not None else [],
        "correlation": correlation_data,
        "categorical_data": cat_data,
        "health_score": health_score,
    }
