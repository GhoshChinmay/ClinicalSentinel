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
    """Search for a key in the dict using exact match, then partial/contains match.
    Only returns scalar string values — skips lists and nested dicts so the
    recursive extractor can handle them properly."""
    for alias in aliases:
        for k, v in obj.items():
            if k.lower() == alias and v is not None and isinstance(v, (str, int, float, bool)) and str(v).strip():
                return str(v).strip()
    for alias in aliases:
        for k, v in obj.items():
            if alias in k.lower() and v is not None and isinstance(v, (str, int, float, bool)) and str(v).strip():
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
    results = []
    
    if isinstance(raw_data, list):
        for item in raw_data:
            results.extend(_extract_oia_insights(item))
            
    elif isinstance(raw_data, dict):
        # 1. Try to extract an OIA from this current dictionary level
        if _is_oia_like(list(raw_data.keys())):
            obs = _fuzzy_get(raw_data, _OBSERVATION_KEYS)
            ins = _fuzzy_get(raw_data, _INSIGHT_KEYS)
            act = _fuzzy_get(raw_data, _ACTION_KEYS)
            
            # Ensure it actually has scalar text values for the OIA
            if obs or ins:
                results.append({
                    "observation": obs or "Data pattern detected in the uploaded dataset.",
                    "insight": ins or "This pattern may impact downstream analysis and model training accuracy.",
                    "action": act or "Review the anomalies in the Detection tab and proceed to Cleaning for remediation.",
                })
                
        # 2. Always recurse deeper in case there are nested OIA arrays or wrappers
        for v in raw_data.values():
            if isinstance(v, (list, dict)):
                results.extend(_extract_oia_insights(v))
                
    return results


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

    prompt = f"""You are a senior data architect. Analyze this dataset profile and provide EXACTLY 3 distinct, high-value insights.

{context_block}

CRITICAL: You must provide exactly 3 insights. 
Each must have an 'observation' (what), 'insight' (so what), and 'action' (now what).
Respond ONLY with a JSON array of 3 objects.

Example:
[
  {{"observation": "...", "insight": "...", "action": "..."}},
  {{"observation": "...", "insight": "...", "action": "..."}},
  {{"observation": "...", "insight": "...", "action": "..."}}
]"""

    def _build_fallback():
        """Guaranteed static OIA insights based on the actual data profile."""
        return [
            {
                "observation": f"The anomaly engine flagged {anomaly_count} out of {total_rows} rows as statistically anomalous.",
                "insight": "These outliers represent high-risk data points that could skew aggregate metrics and degrade downstream model accuracy.",
                "action": "Proceed to the 'Cleaning' step and use 'Quarantine' to isolate all flagged records into a secure storage container.",
            },
            {
                "observation": f"Dataset contains {len(columns)} dimensions with a mix of data types and potential correlations.",
                "insight": "Redundant or highly correlated features increase computational overhead and can lead to model overfitting.",
                "action": "Use the 'Visualizer' correlation matrix to identify and prune redundant features before moving to production.",
            },
            {
                "observation": "Baseline data profiling and schema validation for this session is complete and secure.",
                "insight": "Maintaining a clean data contract ensures that your transformation pipeline remains resilient against drift.",
                "action": "Review the final 'Quality Report' to verify that all data governance standards are met for this dataset.",
            },
        ]

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": os.getenv("OLLAMA_MODEL", "llama3"), "prompt": prompt, "format": "json", "stream": False},
            timeout=120,
        )

        if response.status_code == 200:
            response_text = response.json().get("response", "").strip()
            logger.info("Insights Raw LLM Response: %s", response_text[:500])

            if "```" in response_text:
                response_text = re.sub(r"```(?:json)?\s*", "", response_text)
                response_text = response_text.replace("```", "").strip()

            parsed = json.loads(response_text)
            insights_list = _extract_oia_insights(parsed)

            # Ensure we always return exactly 3 insights by padding with fallbacks if needed
            if not insights_list:
                return {"insights": _build_fallback()}
            
            if len(insights_list) < 3:
                fallbacks = _build_fallback()
                # Don't duplicate if fallback observation is already similar to what we got
                for fb in fallbacks:
                    if len(insights_list) >= 3:
                        break
                    # Simple check to avoid exact duplicates
                    if not any(fb["observation"][:20] in i.get("observation", "") for i in insights_list):
                        insights_list.append(fb)
                
                # If still less than 3 (rare), just force add them
                while len(insights_list) < 3:
                    insights_list.append(fallbacks[len(insights_list)])

            return {"insights": insights_list[:3]}
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
