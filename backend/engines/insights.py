"""
DataSentinel — AI Insights Engine
LLM-powered OIA (Observation, Insight, Action) analysis with bulletproof extraction.
"""

import os
import re
import json
import polars as pl
import requests

from utils import _session_dir, logger

# --- KEY ALIASES: every known LLM variant for each OIA field ---
_OBSERVATION_KEYS = ["observation", "observations", "finding", "findings", "data_point", "fact"]
_INSIGHT_KEYS = ["insight", "insights", "analysis", "impact", "interpretation", "implication"]
_ACTION_KEYS = [
    "action", "actions", "recommendation", "recommendations", "recommended_action",
    "recommended_actions", "suggested_action", "next_step", "next_steps",
    "remediation", "resolution", "suggestion", "step",
]


def _fuzzy_get(obj: dict, aliases: list) -> str:
    """Search for a key in the dict using exact match, then partial/contains match."""
    for alias in aliases:
        for k, v in obj.items():
            if k.lower() == alias and v is not None and str(v).strip():
                return str(v).strip()
    for alias in aliases:
        for k, v in obj.items():
            if alias in k.lower() and v is not None and str(v).strip():
                return str(v).strip()
    return ""


def _is_oia_like(keys: list) -> bool:
    lower = [k.lower() for k in keys]
    return (
        any(alias in l for l in lower for alias in _OBSERVATION_KEYS)
        or any(alias in l for l in lower for alias in _INSIGHT_KEYS)
        or any(alias in l for l in lower for alias in _ACTION_KEYS)
    )


def _extract_oia_insights(raw_data) -> list:
    """
    Bulletproof recursive extractor that can dig OIA insight objects out of
    any arbitrarily nested structure the LLM might return.
    """
    if isinstance(raw_data, list):
        valid = []
        for item in raw_data:
            if isinstance(item, dict):
                if _is_oia_like(list(item.keys())):
                    obs = _fuzzy_get(item, _OBSERVATION_KEYS)
                    ins = _fuzzy_get(item, _INSIGHT_KEYS)
                    act = _fuzzy_get(item, _ACTION_KEYS)
                    if obs or ins:
                        valid.append({
                            "observation": obs or "Data pattern detected in the uploaded dataset.",
                            "insight": ins or "This pattern may impact downstream analysis and model training accuracy.",
                            "action": act or "Review the anomalies in the Detection tab and proceed to Cleaning for remediation.",
                        })
                    else:
                        for v in item.values():
                            valid.extend(_extract_oia_insights(v))
                else:
                    for v in item.values():
                        valid.extend(_extract_oia_insights(v))
            elif isinstance(item, list):
                valid.extend(_extract_oia_insights(item))
        return valid

    if isinstance(raw_data, dict):
        if _is_oia_like(list(raw_data.keys())):
            obs = _fuzzy_get(raw_data, _OBSERVATION_KEYS)
            ins = _fuzzy_get(raw_data, _INSIGHT_KEYS)
            act = _fuzzy_get(raw_data, _ACTION_KEYS)
            if obs or ins:
                return [{
                    "observation": obs or "Data pattern detected in the uploaded dataset.",
                    "insight": ins or "This pattern may impact downstream analysis and model training accuracy.",
                    "action": act or "Review the anomalies in the Detection tab and proceed to Cleaning for remediation.",
                }]

        results = []
        for v in raw_data.values():
            results.extend(_extract_oia_insights(v))
        return results

    return []


def _build_rich_context(df_raw: pl.DataFrame) -> str:
    """Build a richer dataset summary to give the LLM more signal."""
    total_rows = len(df_raw)
    columns = df_raw.columns
    anomaly_count = 0
    if "is_anomaly" in df_raw.columns:
        anomaly_count = df_raw.filter(pl.col("is_anomaly") == True).height
    anomaly_pct = round((anomaly_count / total_rows) * 100, 2) if total_rows > 0 else 0

    numeric_cols = [
        c for c, d in zip(df_raw.columns, df_raw.dtypes)
        if d in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]
    ]
    text_cols = [
        c for c, d in zip(df_raw.columns, df_raw.dtypes)
        if d in [pl.Utf8, getattr(pl, "String", pl.Utf8)]
    ]

    stat_lines = []
    for c in numeric_cols[:5]:
        try:
            series = df_raw[c].drop_nulls()
            if len(series) > 0:
                stat_lines.append(
                    f"  - {c}: min={series.min()}, max={series.max()}, mean={series.mean():.2f}, nulls={df_raw[c].null_count()}"
                )
        except Exception:
            pass

    stats_block = "\n".join(stat_lines) if stat_lines else "  (no numeric stats available)"

    return f"""Dataset Context:
- Total Rows: {total_rows}
- Total Columns: {len(columns)}
- Detected Anomalies: {anomaly_count} ({anomaly_pct}%)
- Numeric Columns ({len(numeric_cols)}): {', '.join(numeric_cols[:10])}
- Text Columns ({len(text_cols)}): {', '.join(text_cols[:10])}
- Key Statistics:
{stats_block}
- All Column Names: {', '.join(columns)}"""


def generate_insights(session_id: str):
    session_dir = _session_dir(session_id)
    raw_path = f"{session_dir}/raw_data.parquet"

    if not os.path.exists(raw_path):
        return {"error": "Data not found"}

    df_raw = pl.read_parquet(raw_path)
    total_rows = len(df_raw)
    columns = df_raw.columns
    anomaly_count = 0
    if "is_anomaly" in df_raw.columns:
        anomaly_count = df_raw.filter(pl.col("is_anomaly") == True).height

    context_block = _build_rich_context(df_raw)

    prompt = f"""You are an elite Data Science Consultant. Analyze this dataset and provide exactly 3 critical insights.

{context_block}

RESPOND WITH ONLY A RAW JSON ARRAY. No markdown, no explanation, no wrapper object.
Use this exact schema:
[
  {{"observation": "...", "insight": "...", "action": "..."}},
  {{"observation": "...", "insight": "...", "action": "..."}},
  {{"observation": "...", "insight": "...", "action": "..."}}
]"""

    def _build_fallback():
        """Guaranteed static OIA insights based on the actual data profile."""
        return [
            {
                "observation": f"The anomaly detection engine flagged {anomaly_count} out of {total_rows} rows ({round(anomaly_count / max(total_rows, 1) * 100, 1)}%) as statistically anomalous.",
                "insight": "These outliers will disproportionately skew aggregate statistics (mean, variance) and degrade the performance of downstream ML models if left untreated.",
                "action": "Navigate to the Cleaning tab and select 'Quarantine' to safely isolate these rows into a forensic vault without permanently deleting them.",
            },
            {
                "observation": f"The dataset contains {len(columns)} distinct features spanning numeric, categorical, and potentially temporal dimensions.",
                "insight": "High dimensionality increases the risk of the 'curse of dimensionality' — models struggle to find signal in noisy, wide datasets. Correlated features also inflate model complexity.",
                "action": "Use the Visualizer tab to inspect the correlation heatmap and identify redundant or highly correlated features that can be safely dropped before modeling.",
            },
            {
                "observation": f"Data profiling across all {total_rows} rows completed successfully. The schema includes columns: {', '.join(columns[:6])}{'...' if len(columns) > 6 else ''}.",
                "insight": "Proper schema validation and anomaly isolation before modeling ensures that your training pipeline receives clean, statistically sound inputs — directly improving accuracy and reducing false positives.",
                "action": "After cleaning, export the sanitized CSV from the Edit tab to ensure all engineered features are stripped and only original columns remain in the final output.",
            },
        ]

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "phi3", "prompt": prompt, "format": "json", "stream": False},
            timeout=120,
        )

        if response.status_code == 200:
            response_text = response.json().get("response", "").strip()
            logger.info("Insights Raw LLM Response: %s", response_text[:500])

            if "```" in response_text:
                response_text = re.sub(r"```(?:json)?\s*", "", response_text)
                response_text = response_text.strip()

            parsed = json.loads(response_text)
            insights_list = _extract_oia_insights(parsed)

            if insights_list and len(insights_list) > 0:
                logger.info("Successfully extracted %d OIA insights.", len(insights_list))
                return {"insights": insights_list}
            else:
                logger.info("LLM returned valid JSON but no OIA objects found. Using fallback.")
                return {"insights": _build_fallback()}
        else:
            raise Exception(f"Local LLM returned status {response.status_code}")

    except json.JSONDecodeError as je:
        logger.warning("Insights JSON Parse Error: %s", je)
        return {"insights": _build_fallback()}
    except requests.exceptions.ConnectionError:
        logger.info("Ollama is not running. Using intelligent fallback.")
        return {"insights": _build_fallback()}
    except requests.exceptions.Timeout:
        logger.info("LLM request timed out. Using fallback.")
        return {"insights": _build_fallback()}
    except Exception as e:
        logger.warning("Insights Error: %s", e)
        return {"insights": _build_fallback()}
