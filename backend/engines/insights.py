"""
DataSentinel — AI Insights Engine (Groq Cloud-Accelerated)
Generates a rich, data-driven dashboard payload with statistical profiling,
correlation analysis, missing-data mapping, and AI-generated narrative insights.

PRIVACY GUARANTEE: Only computed statistics (numbers) are sent to the Groq API.
Raw row data never leaves the local machine.
"""

import os
import json
import math
import polars as pl
import numpy as np

from utils import _session_dir, logger
from groq_client import groq_chat, MODEL_FAST

# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

# Columns injected by the detection pipeline — exclude from user-facing profiles
# BUG FIX: Removed "Class" from this list. It is a valid user column, which was
# causing the 31 vs 30 column count inconsistency!
_INTERNAL_COLS = {
    "is_anomaly",
    "Threat_Score",
    "AI_Reason",
    "SHAP_Payload",
    "logic_violation",
}
_ENGINEERED_SUFFIXES = (
    "_freq",
    "_length",
    "_digit_ratio",
    "_upper_ratio",
    "_special_ratio",
)
_ENGINEERED_PREFIXES = ("nlp_pc",)
_VELOCITY_COLS = {"velocity_24h_sum", "velocity_1h_count"}


def _is_user_column(col: str) -> bool:
    """Return True if the column is an original user column (not internal/engineered)."""
    if col in _INTERNAL_COLS or col in _VELOCITY_COLS:
        return False
    if col.endswith(_ENGINEERED_SUFFIXES):
        return False
    if any(col.startswith(p) for p in _ENGINEERED_PREFIXES):
        return False
    return True


def _safe(val) -> float | None:
    """Convert a value to a JSON-safe float, or None."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 4)
    except (TypeError, ValueError):
        return None


def _compute_skewness(series: pl.Series) -> float | None:
    """Compute skewness for a numeric series."""
    try:
        vals = series.drop_nulls().to_numpy().astype(float)
        n = len(vals)
        if n < 3:
            return None
        mean = np.mean(vals)
        std = np.std(vals, ddof=1)
        if std == 0:
            return 0.0
        skew = (n / ((n - 1) * (n - 2))) * np.sum(((vals - mean) / std) ** 3)
        return round(float(skew), 2)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENGINE
# ─────────────────────────────────────────────────────────────────────────────


def generate_insights(session_id: str) -> dict:
    session_dir = _session_dir(session_id)
    raw_path = f"{session_dir}/raw_data.parquet"

    if not os.path.exists(raw_path):
        return {"error": "Data not found"}

    df = pl.read_parquet(raw_path)
    total_rows = len(df)

    # ── Categorize columns ────────────────────────────────────────────────
    user_cols = [c for c in df.columns if _is_user_column(c)]

    numeric_cols = []
    text_cols = []
    date_cols = []

    for c in user_cols:
        dtype = df[c].dtype
        dtype_str = str(dtype)
        if "Int" in dtype_str or "Float" in dtype_str:
            numeric_cols.append(c)
        elif "Date" in dtype_str or "Time" in dtype_str:
            date_cols.append(c)
        elif "Utf8" in dtype_str or "String" in dtype_str:
            text_cols.append(c)

    # ── Anomaly stats ─────────────────────────────────────────────────────
    anomaly_count = 0
    if "is_anomaly" in df.columns:
        anomaly_count = df.filter(pl.col("is_anomaly") == True).height

    anomaly_rate = round((anomaly_count / total_rows) * 100, 2) if total_rows > 0 else 0

    # ── Summary ───────────────────────────────────────────────────────────
    summary = {
        "total_rows": total_rows,
        "total_columns": len(user_cols),
        "numeric_columns": len(numeric_cols),
        "text_columns": len(text_cols),
        "date_columns": len(date_cols),
        "anomaly_count": anomaly_count,
        "anomaly_rate": anomaly_rate,
    }

    # ── Column profiles (numeric) ─────────────────────────────────────────
    column_profiles = []
    for c in numeric_cols:
        series = df[c].drop_nulls()
        n = len(series)
        null_count = df[c].null_count()

        # Outlier count: values beyond 3σ from mean
        outlier_count = 0
        if n > 2:
            try:
                mean_val = float(series.mean())
                std_val = float(series.std())
                if std_val > 0:
                    outlier_count = int(
                        series.filter(
                            (pl.lit(True))
                            & (((series - mean_val).abs() > (3 * std_val)))
                        ).len()
                    )
            except Exception:
                pass

        profile = {
            "name": c,
            "type": "numeric",
            "min": _safe(series.min()) if n > 0 else None,
            "max": _safe(series.max()) if n > 0 else None,
            "mean": _safe(series.mean()) if n > 0 else None,
            "median": _safe(series.median()) if n > 0 else None,
            "std": _safe(series.std()) if n > 0 else None,
            "null_count": null_count,
            "null_pct": (
                round((null_count / total_rows) * 100, 2) if total_rows > 0 else 0
            ),
            "skewness": _compute_skewness(series),
            "outlier_count": outlier_count,
        }
        column_profiles.append(profile)

    # ── Text column profiles ──────────────────────────────────────────────
    for c in text_cols:
        null_count = df[c].null_count()
        unique_count = df[c].n_unique()
        column_profiles.append(
            {
                "name": c,
                "type": "text",
                "unique_values": unique_count,
                "null_count": null_count,
                "null_pct": (
                    round((null_count / total_rows) * 100, 2) if total_rows > 0 else 0
                ),
            }
        )

    # ── Missing data map ──────────────────────────────────────────────────
    missing_data_map = []
    for c in user_cols:
        nc = df[c].null_count()
        if nc > 0:
            missing_data_map.append(
                {
                    "column": c,
                    "null_count": nc,
                    "null_pct": round((nc / total_rows) * 100, 2),
                }
            )
    missing_data_map.sort(key=lambda x: x["null_count"], reverse=True)

    # ── Type breakdown ────────────────────────────────────────────────────
    type_breakdown = {
        "numeric": len(numeric_cols),
        "text": len(text_cols),
        "date": len(date_cols),
    }

    # ── Top correlations ──────────────────────────────────────────────────
    top_correlations = []
    if len(numeric_cols) > 1:
        try:
            corr_df = df.select(numeric_cols).to_pandas().corr().fillna(0)
            pairs_seen = set()
            for i, col_a in enumerate(numeric_cols):
                for j, col_b in enumerate(numeric_cols):
                    if i >= j:
                        continue
                    pair_key = tuple(sorted([col_a, col_b]))
                    if pair_key in pairs_seen:
                        continue
                    pairs_seen.add(pair_key)
                    val = float(corr_df.iloc[i, j])
                    if abs(val) > 0.3:
                        top_correlations.append(
                            {
                                "col_a": col_a,
                                "col_b": col_b,
                                "value": round(val, 3),
                            }
                        )
            top_correlations.sort(key=lambda x: abs(x["value"]), reverse=True)
            top_correlations = top_correlations[:10]
        except Exception as e:
            logger.warning("Correlation computation failed: %s", e)

    # ── Anomaly distribution by column ────────────────────────────────────
    anomaly_distribution = []
    if (
        anomaly_count > 0
        and "is_anomaly" in df.columns
        and "Threat_Score" in df.columns
    ):
        anomaly_df = df.filter(pl.col("is_anomaly") == True)
        for c in numeric_cols:
            try:
                series = anomaly_df[c].drop_nulls()
                full_series = df[c].drop_nulls()
                if len(full_series) > 2 and len(series) > 0:
                    mean_val = float(full_series.mean())
                    std_val = float(full_series.std())
                    if std_val > 0:
                        outlier_in_anomalies = int(
                            series.filter(
                                ((series - mean_val).abs() > (2 * std_val))
                            ).len()
                        )
                        if outlier_in_anomalies > 0:
                            anomaly_distribution.append(
                                {
                                    "column": c,
                                    "anomaly_count": outlier_in_anomalies,
                                }
                            )
            except Exception:
                pass
        anomaly_distribution.sort(key=lambda x: x["anomaly_count"], reverse=True)
        anomaly_distribution = anomaly_distribution[:10]

    # ── AI Narrative (via Groq — ONLY statistics sent, never raw data) ────
    ai_narrative = _generate_ai_narrative(
        summary, column_profiles, top_correlations, missing_data_map
    )

    return {
        "summary": summary,
        "column_profiles": column_profiles,
        "missing_data_map": missing_data_map,
        "type_breakdown": type_breakdown,
        "top_correlations": top_correlations,
        "anomaly_distribution": anomaly_distribution,
        "ai_narrative": ai_narrative,
    }


def _generate_ai_narrative(
    summary: dict,
    column_profiles: list[dict],
    top_correlations: list[dict],
    missing_data_map: list[dict],
) -> list[str]:
    """
    Generate 3-5 human-readable insight sentences using Groq.
    ONLY computed statistics are sent — never raw data values.
    """
    # Build a statistics-only context block for the LLM
    stats_context = f"""Dataset Statistics:
- Rows: {summary['total_rows']} | Columns: {summary['total_columns']}
- Numeric: {summary['numeric_columns']} | Text: {summary['text_columns']} | Date: {summary['date_columns']}
- Anomalies: {summary['anomaly_count']} ({summary['anomaly_rate']}%)
"""

    # Add top numeric profiles
    numeric_profiles = [p for p in column_profiles if p.get("type") == "numeric"]
    if numeric_profiles:
        stats_context += "\nNumeric Column Summaries:\n"
        for p in numeric_profiles[:8]:
            stats_context += f"  - {p['name']}: min={p.get('min')}, max={p.get('max')}, mean={p.get('mean')}, std={p.get('std')}, skew={p.get('skewness')}, nulls={p.get('null_count')}, outliers={p.get('outlier_count')}\n"

    # Add correlation info
    if top_correlations:
        stats_context += "\nTop Correlations:\n"
        for c in top_correlations[:5]:
            stats_context += f"  - {c['col_a']} ↔ {c['col_b']}: r={c['value']}\n"

    # Add missing data info
    if missing_data_map:
        stats_context += "\nMissing Data:\n"
        for m in missing_data_map[:5]:
            stats_context += (
                f"  - {m['column']}: {m['null_count']} nulls ({m['null_pct']}%)\n"
            )

    prompt = f"""You are a senior data analyst. Given ONLY these computed statistics about a dataset, generate exactly 4 distinct, specific, actionable insights.

{stats_context}

RULES:
1. Each insight must be ONE sentence, clear and specific.
2. Reference actual column names and numbers from the statistics.
3. Focus on: data quality issues, interesting patterns, correlations, skewness, outliers, and missing data.
4. Do NOT make generic statements. Every insight MUST reference specific statistics.
5. Respond with a JSON object: {{"insights": ["insight1", "insight2", "insight3", "insight4"]}}"""

    messages = [
        {
            "role": "system",
            "content": "You are a JSON-only data analysis API. Respond with valid JSON only.",
        },
        {"role": "user", "content": prompt},
    ]

    try:
        from groq_client import groq_chat_json

        result = groq_chat_json(messages, model=MODEL_FAST, temperature=0.3, timeout=12)
        if result and isinstance(result, dict):
            insights = result.get("insights", [])
            if isinstance(insights, list) and len(insights) > 0:
                return [
                    str(i).strip() for i in insights if isinstance(i, str) and i.strip()
                ][:5]
    except Exception as e:
        logger.warning("AI narrative generation failed: %s", e)

    # Intelligent fallback — generate insights from computed stats
    return _build_fallback_narrative(
        summary, column_profiles, top_correlations, missing_data_map
    )


def _build_fallback_narrative(
    summary: dict,
    column_profiles: list[dict],
    top_correlations: list[dict],
    missing_data_map: list[dict],
) -> list[str]:
    """Generate meaningful insights from raw statistics when LLM is unavailable."""
    narratives = []

    # Anomaly insight
    if summary["anomaly_count"] > 0:
        narratives.append(
            f"The anomaly detection engine flagged {summary['anomaly_count']} out of "
            f"{summary['total_rows']} rows ({summary['anomaly_rate']}%) as statistically anomalous."
        )

    # Skewness insight
    numeric_profiles = [
        p for p in column_profiles if p.get("type") == "numeric" and p.get("skewness")
    ]
    skewed = [p for p in numeric_profiles if abs(p["skewness"] or 0) > 2]
    if skewed:
        worst = max(skewed, key=lambda p: abs(p["skewness"] or 0))
        narratives.append(
            f"Column '{worst['name']}' shows extreme skewness ({worst['skewness']}), "
            f"with {worst.get('outlier_count', 0)} outliers beyond 3 standard deviations — "
            f"consider log-transformation or winsorization before modelling."
        )

    # Correlation insight
    if top_correlations:
        top = top_correlations[0]
        direction = "positive" if top["value"] > 0 else "negative"
        narratives.append(
            f"Strong {direction} correlation detected between '{top['col_a']}' and "
            f"'{top['col_b']}' (r={top['value']}), which may indicate redundancy or a causal relationship."
        )

    # Missing data insight
    if missing_data_map:
        worst_missing = missing_data_map[0]
        narratives.append(
            f"Missing data is concentrated in '{worst_missing['column']}' "
            f"({worst_missing['null_count']} nulls, {worst_missing['null_pct']}%), "
            f"which may impact downstream model accuracy if left unaddressed."
        )

    # Size/dimension insight
    if not narratives or len(narratives) < 3:
        narratives.append(
            f"Dataset contains {summary['total_columns']} features across {summary['total_rows']} observations "
            f"with a mix of {summary['numeric_columns']} numeric and {summary['text_columns']} categorical dimensions."
        )

    return narratives[:5]
