"""
ClinicalSentinel — CohortDrift Engine (Feature F5)
Intra-trial temporal cohort drift detector.
Splits an investigator's data into chronological phases and measures 
statistical divergence (KS-Test & PSI) to detect mid-trial fabrication onset.
"""

import numpy as np
import pandas as pd
import polars as pl
from scipy.stats import ks_2samp
from utils import logger

def calculate_psi(expected_array, actual_array, buckets=10) -> float:
    """
    Calculates Population Stability Index (PSI) between two arrays.
    PSI > 0.2 indicates significant population shift (high fabrication risk).
    """
    if len(expected_array) < 10 or len(actual_array) < 10:
        return 0.0

    # Define the bin edges based on the expected (Phase 1) distribution
    breakpoints = np.arange(0, buckets + 1) / buckets * 100
    try:
        expected_perc = np.percentile(expected_array, breakpoints)
    except Exception:
        return 0.0

    expected_perc[0] = -np.inf
    expected_perc[-1] = np.inf

    expected_counts = np.histogram(expected_array, expected_perc)[0]
    actual_counts = np.histogram(actual_array, expected_perc)[0]

    # Convert counts to fractions
    expected_fractions = expected_counts / len(expected_array)
    actual_fractions = actual_counts / len(actual_array)

    # Avoid division by zero
    expected_fractions = np.where(expected_fractions == 0, 0.0001, expected_fractions)
    actual_fractions = np.where(actual_fractions == 0, 0.0001, actual_fractions)

    # PSI Formula
    psi = np.sum((actual_fractions - expected_fractions) * np.log(actual_fractions / expected_fractions))
    return round(float(psi), 4)


def detect_cohort_drift(df: pl.DataFrame, time_col: str, investigator_col: str, metric_cols: list[str]) -> dict:
    """
    Splits data temporally and measures intra-investigator drift.
    Returns a dictionary of Phase Drift Scores (PDS) keyed by Investigator ID.
    """
    logger.info("Initializing CohortDrift Phase Shift Analysis...")
    drift_reports = {}

    try:
        pandas_df = df.to_pandas()
        
        # Ensure we have valid timestamps
        pandas_df[time_col] = pd.to_datetime(pandas_df[time_col], errors='coerce')
        pandas_df = pandas_df.dropna(subset=[time_col, investigator_col])
        
        if pandas_df.empty:
            return drift_reports

        # Group by Investigator
        grouped = pandas_df.groupby(investigator_col)

        for investigator, group_df in grouped:
            if len(group_df) < 30:
                continue # Not enough data to track temporal drift
            
            # Chronologically sort the investigator's entries
            group_df = group_df.sort_values(by=time_col)
            
            # Split into 3 phases: Enrollment (1), Mid (2), Endpoint (3)
            phase_size = len(group_df) // 3
            phase_1 = group_df.iloc[:phase_size]
            phase_3 = group_df.iloc[-phase_size:]
            
            investigator_drift = {"max_psi": 0.0, "flagged_metrics": [], "phase_drift_score": 0.0, "phase_plot_json": None}
            
            best_metric_for_plot = None
            highest_psi_for_plot = 0.0
            
            for metric in metric_cols:
                if metric not in group_df.columns:
                    continue
                    
                p1_vals = phase_1[metric].dropna().values
                p3_vals = phase_3[metric].dropna().values
                
                if len(p1_vals) < 10 or len(p3_vals) < 10:
                    continue
                
                # 1. KS-Test for distribution shape shift
                ks_stat, p_value = ks_2samp(p1_vals, p3_vals)
                
                # 2. Population Stability Index (PSI) for magnitude shift
                psi_score = calculate_psi(p1_vals, p3_vals)
                
                investigator_drift["max_psi"] = max(investigator_drift["max_psi"], psi_score)
                
                # If PSI > 0.2 (Significant Shift) AND p-val < 0.05 (Statistically proven)
                if psi_score > 0.2 and p_value < 0.05:
                    investigator_drift["flagged_metrics"].append({
                        "metric": metric,
                        "psi": psi_score,
                        "p_value": round(p_value, 5)
                    })
                    
                    if psi_score > highest_psi_for_plot:
                        highest_psi_for_plot = psi_score
                        best_metric_for_plot = metric
            
            # Generate Plotly JSON for the most drifted metric
            if best_metric_for_plot:
                try:
                    import plotly.graph_objects as go
                    import json
                    fig = go.Figure()
                    fig.add_trace(go.Histogram(x=phase_1[best_metric_for_plot].dropna(), name='Phase 1 (Early)', opacity=0.7, histnorm='probability'))
                    fig.add_trace(go.Histogram(x=phase_3[best_metric_for_plot].dropna(), name='Phase 3 (Late)', opacity=0.7, histnorm='probability'))
                    fig.update_layout(barmode='overlay', title=f"Cohort Drift: {best_metric_for_plot}", xaxis_title=best_metric_for_plot, yaxis_title="Probability")
                    investigator_drift["phase_plot_json"] = json.loads(fig.to_json())
                except Exception as e:
                    logger.warning(f"Plotly generation failed for {investigator}: {e}")
            
            # Calculate Phase Drift Score (PDS)
            # A PDS of 100 means extreme mid-trial behavioral change
            if investigator_drift["flagged_metrics"]:
                base_score = min((investigator_drift["max_psi"] / 0.5) * 100, 100.0)
                investigator_drift["phase_drift_score"] = round(base_score, 1)
                drift_reports[str(investigator)] = investigator_drift
                
        logger.info(f"CohortDrift analysis complete. Found {len(drift_reports)} investigators with temporal drift.")
        return drift_reports

    except Exception as e:
        logger.warning(f"CohortDrift engine failed: {e}")
        return {}