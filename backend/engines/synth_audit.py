"""
ClinicalSentinel — SynthAudit Engine (Feature F6)
Statistically-correct synthetic reference twin for ground-truth comparison.
Uses Gaussian Copulas (via SDV) to generate a "perfect" baseline distribution
and measures investigator deviation (Synthetic Deviation Score - SDS).
"""

import pandas as pd
import numpy as np
import polars as pl
from scipy.stats import ks_2samp
from utils import logger

try:
    from sdv.metadata import SingleTableMetadata
    from sdv.single_table import GaussianCopulaSynthesizer
    SDV_AVAILABLE = True
except ImportError:
    SDV_AVAILABLE = False


def generate_synthetic_twin(df_pandas: pd.DataFrame, continuous_cols: list[str]) -> pd.DataFrame:
    """
    Fits a Gaussian Copula to the continuous columns to learn the underlying 
    mathematical covariance and generates a clean synthetic reference dataset.
    """
    logger.info("Training Gaussian Copula to generate Protocol-Grounded Synthetic Twin...")
    
    # We only train on continuous clinical metrics (e.g., Blood Pressure, Heart Rate, Age)
    train_data = df_pandas[continuous_cols].dropna()
    
    if len(train_data) < 50:
        raise ValueError("Not enough clean data to generate a stable synthetic twin.")
        
    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(train_data)
    
    # Gaussian Copula preserves multi-variate correlations perfectly
    synthesizer = GaussianCopulaSynthesizer(metadata)
    synthesizer.fit(train_data)
    
    # Generate a reference twin of exactly 1,000 "perfect" patients
    synthetic_data = synthesizer.sample(num_rows=1000)
    logger.info("Synthetic Ghost Site generated successfully.")
    
    return synthetic_data


def audit_against_synthetic(df: pl.DataFrame, investigator_col: str, metric_cols: list[str]) -> dict:
    """
    Generates a synthetic baseline, then runs KS-Tests to measure how far 
    each real investigator deviates from the mathematical ideal.
    """
    if not SDV_AVAILABLE:
        logger.warning("SDV not installed. Skipping SynthAudit. Run: pip install sdv")
        return {"error": "Missing SDV library."}
        
    logger.info("Initializing SynthAudit Deviation Analysis...")
    audit_reports = {}
    
    try:
        pandas_df = df.to_pandas()
        
        # Filter for valid numeric targets with enough variance
        target_metrics = [c for c in metric_cols if c in pandas_df.columns and pandas_df[c].nunique() > 5]
        
        if not target_metrics or investigator_col not in pandas_df.columns:
            return {"status": "Missing required metrics or investigator mapping."}
            
        # 1. Generate the Ghost Site (Synthetic Reference)
        try:
            if "Threat_Score" in pandas_df.columns:
                inv_scores = pandas_df.groupby(investigator_col)["Threat_Score"].mean()
                num_clean = max(1, int(len(inv_scores) * 0.4))
                cleanest_invs = inv_scores.nsmallest(num_clean).index
                train_data = pandas_df[pandas_df[investigator_col].isin(cleanest_invs)]
                logger.info(f"Training SynthAudit on cleanest 40% of investigators (N={len(cleanest_invs)}).")
            else:
                train_data = pandas_df
                logger.warning("Threat_Score not found. Training SynthAudit on all data.")
                
            synthetic_reference = generate_synthetic_twin(train_data, target_metrics)
        except Exception as e:
            logger.warning(f"Failed to generate synthetic twin: {e}")
            return {}
            
        # 2. Compare every real doctor to the Ghost Site
        grouped = pandas_df.groupby(investigator_col)
        
        for investigator, group_df in grouped:
            if len(group_df) < 20:
                continue # Skip low-volume investigators
                
            investigator_deviations = []
            cumulative_sds = 0.0 # Synthetic Deviation Score
            
            for metric in target_metrics:
                real_vals = group_df[metric].dropna().values
                synth_vals = synthetic_reference[metric].dropna().values
                
                if len(real_vals) < 10 or len(synth_vals) < 10:
                    continue
                    
                # Compare Real vs Synthetic using KS-Test
                ks_stat, p_value = ks_2samp(real_vals, synth_vals)
                
                # If they deviate heavily from the "perfect" distribution
                if ks_stat > 0.25 and p_value < 0.05:
                    deviation_score = round(ks_stat * 100, 1)
                    cumulative_sds += deviation_score
                    
                    investigator_deviations.append({
                        "metric": metric,
                        "deviation_magnitude": deviation_score,
                        "p_value": round(p_value, 5)
                    })
                    
            if investigator_deviations:
                # Average the deviation across all flagged metrics
                final_sds = round(cumulative_sds / len(target_metrics), 1)
                
                # SDS > 30 implies severe manipulation (their data looks nothing like the protocol expectation)
                if final_sds > 20.0:
                    audit_reports[str(investigator)] = {
                        "synthetic_deviation_score": final_sds,
                        "flagged_metrics": investigator_deviations,
                        "warning": f"Data distribution deviates heavily from protocol-grounded synthetic baseline (SDS: {final_sds})."
                    }
                    
        logger.info(f"SynthAudit complete. Flagged {len(audit_reports)} investigators with high Synthetic Deviation.")
        return audit_reports

    except Exception as e:
        logger.warning(f"SynthAudit engine failed: {e}")
        return {}