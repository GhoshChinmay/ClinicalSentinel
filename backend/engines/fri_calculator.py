"""
ClinicalSentinel — Composite FRI (Fabrication Risk Index) Calculator
Aggregates scores from all 7 forensic detection layers into a single,
defensible per-investigator risk score (0–100).

FRI is the core patentable output of ClinicalSentinel.
Each layer is independently significant; the composite is uniquely powerful.

Layer Weights (validated against JMIR fraud literature):
  Layer 1 — Benford's Law:           25% (strongest mathematical signal)
  Layer 2 — Temporal Burst:          20% (timestamp evidence)
  Layer 3 — Statistical Outlier:     15% (baseline detection engine)
  Layer 4 — Round-Number Preference: 10% (subconscious human fabrication)
  Layer 5 — Last-Digit Entropy:      10% (subconscious bias detection)
  Layer 6 — Clinical Plausibility:   10% (biological reality check)
  Layer 7 — Behavioral Profile BAE:  10% (longitudinal behavioral shift)
"""

import os
import json

import polars as pl
import pandas as pd
import numpy as np
from utils import logger, _BACKEND_DIR
from groq_client import groq_chat

# ─────────────────────────────────────────────────────────────────────────────
# LAYER WEIGHTS (must sum to 1.0)
# ─────────────────────────────────────────────────────────────────────────────
_WEIGHTS = {
    "benford":       0.25,  # Layer 1
    "temporal":      0.20,  # Layer 2
    "statistical":   0.15,  # Layer 3
    "round_number":  0.10,  # Layer 4
    "entropy":       0.10,  # Layer 5
    "plausibility":  0.10,  # Layer 6
    "behavioral":    0.10,  # Layer 7 (InvestiProfile BAEs)
}

_RISK_BANDS = {
    "high":   (66, 100, "🔴 High Fabrication Risk"),
    "review": (36, 65,  "🟡 Needs Audit Review"),
    "low":    (0,  35,  "🟢 Low Risk — Likely Clean"),
}


def _get_risk_band(score: float) -> dict:
    """Map a numeric FRI score to its labeled risk band."""
    for band_key, (lo, hi, label) in _RISK_BANDS.items():
        if lo <= score <= hi:
            return {"band": band_key, "label": label}
    return {"band": "unknown", "label": "⚪ Insufficient Data"}


def calculate_composite_fri(
    df: pl.DataFrame,
    investigator_col: str,
    time_col: str | None = None,
    metric_cols: list[str] | None = None,
    shared_attr_cols: list[str] | None = None,
) -> dict:
    """
    Runs all available forensic layers against the dataset and calculates
    a composite Fabrication Risk Index (FRI) per investigator.
    """
    logger.info("═══ Starting Composite FRI Calculation for all investigators ═══")
    results = {}

    pandas_df = df.to_pandas()
    if investigator_col not in pandas_df.columns:
        logger.warning(f"FRI Calculator: investigator column '{investigator_col}' not found.")
        return {}

    metric_cols = metric_cols or []
    shared_attr_cols = shared_attr_cols or []

    # ─────────────────────────────────────────────────────────────────────────
    # LAYER 1 & 4 & 5 — Clinical Math (Benford, Round, Entropy)
    # ─────────────────────────────────────────────────────────────────────────
    from engines.clinical_math import (
        calculate_benfords_law_score,
        calculate_round_number_risk,
        calculate_last_digit_entropy,
    )

    layer1_scores = {}  
    layer4_scores = {}  
    layer5_scores = {}  

    grouped = pandas_df.groupby(investigator_col)
    clinical_targets = [c for c in metric_cols if c in pandas_df.columns and pandas_df[c].nunique() > 10][:5]

    for investigator, grp in grouped:
        inv_id = str(investigator)
        b_scores, r_scores, e_scores = [], [], []
        for col in clinical_targets:
            series = grp[col].dropna()
            if len(series) >= 20:
                b_scores.append(calculate_benfords_law_score(series)["risk_score"])
                r_scores.append(calculate_round_number_risk(series)["risk_score"])
                e_scores.append(calculate_last_digit_entropy(series)["risk_score"])
        layer1_scores[inv_id] = float(np.mean(b_scores)) if b_scores else 0.0
        layer4_scores[inv_id] = float(np.mean(r_scores)) if r_scores else 0.0
        layer5_scores[inv_id] = float(np.mean(e_scores)) if e_scores else 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # LAYER 3 — Statistical Outlier (Threat_Score from Isolation Forest)
    # ─────────────────────────────────────────────────────────────────────────
    layer3_scores = {}
    if "Threat_Score" in pandas_df.columns:
        for investigator, grp in grouped:
            layer3_scores[str(investigator)] = float(grp["Threat_Score"].mean())

    # ─────────────────────────────────────────────────────────────────────────
    # LAYER 6 — Clinical Plausibility (logic_violation from Logic Gate)
    # ─────────────────────────────────────────────────────────────────────────
    layer6_scores = {}
    if "logic_violation" in pandas_df.columns:
        for investigator, grp in grouped:
            violation_rate = grp["logic_violation"].notna().sum() / max(len(grp), 1)
            layer6_scores[str(investigator)] = min(violation_rate * 100, 100.0)

    # ─────────────────────────────────────────────────────────────────────────
    # LAYER 2 + LAYER 7 — Temporal Burst & InvestiProfile (requires time_col)
    # ─────────────────────────────────────────────────────────────────────────
    layer2_scores = {}  
    layer7_scores = {}  
    bae_events_map = {}

    if time_col and time_col in pandas_df.columns:
        try:
            from engines.investi_profile import detect_behavioral_anomalies
            bae_results = detect_behavioral_anomalies(df, time_col, investigator_col)
            for inv_id, report in bae_results.items():
                bae_count = report.get("bae_count", 0)
                layer7_scores[inv_id] = min(bae_count * 30, 100.0)
                bae_events_map[inv_id] = report.get("events", [])
        except Exception as e:
            logger.warning(f"FRI: InvestiProfile layer failed: {e}")

        try:
            temp_df = pandas_df.copy()
            temp_df[time_col] = pd.to_datetime(temp_df[time_col], errors="coerce")
            temp_df = temp_df.dropna(subset=[time_col])
            for investigator, grp in temp_df.groupby(investigator_col):
                grp_sorted = grp.sort_values(by=time_col)
                grp_sorted = grp_sorted.set_index(time_col)
                hourly = grp_sorted.resample("1h").size()
                max_hourly = hourly.max() if len(hourly) > 0 else 0
                
                if max_hourly > 30:
                    layer2_scores[str(investigator)] = 100.0
                elif max_hourly > 15:
                    layer2_scores[str(investigator)] = 65.0
                elif max_hourly > 10:
                    layer2_scores[str(investigator)] = 35.0
                else:
                    layer2_scores[str(investigator)] = 0.0
        except Exception as e:
            logger.warning(f"FRI: Temporal burst layer failed: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # F5 — CohortDrift Phase Drift Scores
    # ─────────────────────────────────────────────────────────────────────────
    pds_scores = {}
    if time_col and clinical_targets:
        try:
            from engines.cohort_drift import detect_cohort_drift
            drift_results = detect_cohort_drift(df, time_col, investigator_col, clinical_targets)
            for inv_id, report in drift_results.items():
                pds_scores[inv_id] = report.get("phase_drift_score", 0.0)
        except Exception as e:
            logger.warning(f"FRI: CohortDrift layer failed: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # F6 — SynthAudit Synthetic Deviation Scores
    # ─────────────────────────────────────────────────────────────────────────
    sds_scores = {}
    if clinical_targets:
        try:
            from engines.synth_audit import audit_against_synthetic
            synth_results = audit_against_synthetic(df, investigator_col, clinical_targets)
            for inv_id, report in synth_results.items():
                if isinstance(report, dict) and "synthetic_deviation_score" in report:
                    sds_scores[inv_id] = min(report["synthetic_deviation_score"], 100.0)
        except Exception as e:
            logger.warning(f"FRI: SynthAudit layer failed: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # F2 — GNN Collusion Risk Cluster Scores
    # ─────────────────────────────────────────────────────────────────────────
    crcs_scores = {}
    if shared_attr_cols:
        try:
            from engines.gnn_collusion import detect_collusion_networks
            gnn_results = detect_collusion_networks(df, investigator_col, shared_attr_cols)
            for inv_id, report in gnn_results.items():
                if isinstance(report, dict) and "CRCS_score" in report:
                    crcs_scores[inv_id] = report["CRCS_score"]
        except Exception as e:
            logger.warning(f"FRI: GNN Collusion layer failed: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # COMPOSITE FRI AGGREGATION
    # ─────────────────────────────────────────────────────────────────────────
    all_investigators = pandas_df[investigator_col].dropna().unique()

    # Layer breakdown placeholder keys
    _EMPTY_LAYERS = {
        "L1_benfords_law": 0.0, "L2_temporal_burst": 0.0,
        "L3_statistical_outlier": 0.0, "L4_round_number": 0.0,
        "L5_last_digit_entropy": 0.0, "L6_clinical_plausibility": 0.0,
        "L7_behavioral_profile": 0.0,
    }

    for investigator in all_investigators:
        inv_id = str(investigator)
        entry_count = int((pandas_df[investigator_col] == investigator).sum())

        # Phase 6 fix: skip investigators with insufficient data
        if entry_count < 10:
            results[inv_id] = {
                "investigator_id": inv_id,
                "fri_score": 0.0,
                "risk_band": "low",
                "risk_label": "⚪ Insufficient Data",
                "entry_count": entry_count,
                "layer_breakdown": _EMPTY_LAYERS.copy(),
                "bae_events": [],
                "pds_score": 0.0,
                "sds_score": 0.0,
                "crcs_score": 0.0,
                "note": "Insufficient data (<10 entries for reliable scoring)",
            }
            continue

        l1 = layer1_scores.get(inv_id, 0.0)
        l2 = layer2_scores.get(inv_id, 0.0)
        l3 = layer3_scores.get(inv_id, 0.0)
        l4 = layer4_scores.get(inv_id, 0.0)
        l5 = layer5_scores.get(inv_id, 0.0)
        l6 = layer6_scores.get(inv_id, 0.0)
        l7 = layer7_scores.get(inv_id, 0.0)

        fri = (
            _WEIGHTS["benford"]      * l1 +
            _WEIGHTS["temporal"]     * l2 +
            _WEIGHTS["statistical"]  * l3 +
            _WEIGHTS["round_number"] * l4 +
            _WEIGHTS["entropy"]      * l5 +
            _WEIGHTS["plausibility"] * l6 +
            _WEIGHTS["behavioral"]   * l7
        )
        fri = round(min(fri, 100.0), 1)
        band_info = _get_risk_band(fri)

        results[inv_id] = {
            "investigator_id":  inv_id,
            "fri_score":        fri,
            "risk_band":        band_info["band"],
            "risk_label":       band_info["label"],
            "entry_count":      entry_count,
            "layer_breakdown": {
                "L1_benfords_law":          round(l1, 1),
                "L2_temporal_burst":        round(l2, 1),
                "L3_statistical_outlier":   round(l3, 1),
                "L4_round_number":          round(l4, 1),
                "L5_last_digit_entropy":    round(l5, 1),
                "L6_clinical_plausibility": round(l6, 1),
                "L7_behavioral_profile":    round(l7, 1),
            },
            "bae_events":  bae_events_map.get(inv_id, []),
            "pds_score":   round(pds_scores.get(inv_id, 0.0), 1),
            "sds_score":   round(sds_scores.get(inv_id, 0.0), 1),
            "crcs_score":  round(crcs_scores.get(inv_id, 0.0), 1),
        }
        
        # Phase 6: Groq FRI Narrative
        prompt = f"""
You are a clinical trial forensic auditor. 
Write a 2-sentence regulatory narrative for this investigator.
Investigator: {inv_id}
FRI Score: {fri}/100 (Risk Band: {band_info['band']})
Key factors:
- Benford's Law Score: {l1}
- Temporal Burst Score: {l2}
- Cohort Drift Score: {pds_scores.get(inv_id, 0.0)}
- Synth Deviation Score: {sds_scores.get(inv_id, 0.0)}
- BAE count: {len(bae_events_map.get(inv_id, []))}

If the score is >= 66, state that these signals indicate statistically significant fabrication risk requiring mandatory site audit under ICH E6(R3) Clause 5.18.3.
Do not use markdown. Keep it strictly to 2 sentences.
"""
        narrative = groq_chat([{"role": "user", "content": prompt}])
        results[inv_id]["narrative"] = narrative or "Narrative generation failed."

    sorted_results = dict(
        sorted(results.items(), key=lambda x: x[1]["fri_score"], reverse=True)
    )

    high_risk = sum(1 for v in sorted_results.values() if v["risk_band"] == "high")
    review    = sum(1 for v in sorted_results.values() if v["risk_band"] == "review")
    low_risk  = sum(1 for v in sorted_results.values() if v["risk_band"] == "low")

    logger.info(
        f"FRI Complete: {len(sorted_results)} investigators | "
        f"🔴 High Risk: {high_risk} | 🟡 Needs Review: {review} | 🟢 Low Risk: {low_risk}"
    )

    return {
        "investigators": sorted_results,
        "summary": {
            "total_investigators": len(sorted_results),
            "high_risk_count": high_risk,
            "needs_review_count": review,
            "low_risk_count": low_risk,
            "highest_fri": max((v["fri_score"] for v in sorted_results.values()), default=0),
            "mean_fri": round(
                np.mean([v["fri_score"] for v in sorted_results.values()]), 1
            ) if sorted_results else 0.0,
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# NEW: WRAPPER FOR API ROUTES
# ─────────────────────────────────────────────────────────────────────────────
# ── Internal engine columns that must NOT be treated as clinical metrics ───────
_INTERNAL_COLS: set[str] = {
    "is_anomaly", "Threat_Score", "lof_score", "ecod_score",
    "lstm_anomaly_score", "velocity_24h_sum", "velocity_1h_count",
    "logic_violation",
}
_INTERNAL_SUFFIXES = (
    "_benford_risk", "_round_risk", "_entropy_risk", "_entity_z", "_freq",
    "_z_score", "SHAP_Payload",
)


def calculate_fri_report(
    df: pl.DataFrame,
    session_dir: str | None = None,
    force_refresh: bool = False,
) -> dict:
    """
    Wrapper that auto-detects clinical columns and calls the main FRI calculator.
    Results are cached per session in session_dir/fri_result.json.
    Pass force_refresh=True to bypass cache.
    """
    # ── Cache check ──────────────────────────────────────────────────────────
    if session_dir and not force_refresh:
        cache_path = os.path.join(session_dir, "fri_result.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r") as f:
                    logger.info("FRI: returning cached result.")
                    return json.load(f)
            except Exception:
                pass  # Corrupt cache — recompute

    pandas_df = df.to_pandas()

    # ── Phase 6 fix: smarter column auto-detection ───────────────────────────
    investigator_col = next(
        (col for col in pandas_df.columns
         if any(kw in col.lower() for kw in ["investigator", "doctor", "inv_id", "physician"])),
        None,
    )
    # Fallback: site-based grouping
    if not investigator_col:
        investigator_col = next(
            (col for col in pandas_df.columns if "site" in col.lower()), None
        )

    time_col = next(
        (col for col in pandas_df.columns
         if any(kw in col.lower() for kw in ["timestamp", "entry_time", "date", "time"])),
        None,
    )

    # Exclude ALL internal engine-generated numeric columns
    metric_cols = [
        col for col in pandas_df.select_dtypes(include="number").columns
        if col not in _INTERNAL_COLS
        and not any(col.endswith(sfx) for sfx in _INTERNAL_SUFFIXES)
    ]

    shared_attr_cols = [
        col for col in pandas_df.columns
        if col.lower() in {"country", "cro", "cro_name", "study_phase", "hospital", "site_id", "site"}
    ]

    if not investigator_col:
        logger.warning("No Investigator/Site column found. Cannot compute FRI.")
        return {"error": "Dataset must contain a column indicating the Investigator, Site, or Doctor."}

    result = calculate_composite_fri(
        df=df,
        investigator_col=investigator_col,
        time_col=time_col,
        metric_cols=metric_cols,
        shared_attr_cols=shared_attr_cols,
    )

    # ── Cache the result ─────────────────────────────────────────────────────
    if session_dir:
        try:
            cache_path = os.path.join(session_dir, "fri_result.json")
            with open(cache_path, "w") as f:
                json.dump(result, f)
        except Exception as e:
            logger.warning(f"FRI: failed to write cache: {e}")

    return result