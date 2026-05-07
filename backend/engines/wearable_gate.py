"""
ClinicalSentinel — WearableGate Engine (Feature F3)
Wearable sensor data fabrication authenticator for decentralized trials (DCTs).
Analyzes time-series telemetry (e.g., Heart Rate, SpO2) for biological noise floors,
autocorrelation, and human integer-clustering to prove the data came from a real
hardware sensor and was not manually typed.
"""

import numpy as np
import pandas as pd
import polars as pl
from utils import logger

def _check_noise_floor(vals: np.ndarray) -> float:
    """
    Biological sensors have a natural 'noise floor'. 
    No two consecutive heartbeats are exactly identical (HRV).
    If variance is suspiciously low or exactly zero, it's manually typed.
    """
    if len(vals) < 5:
        return 0.0
        
    variance = np.var(vals)
    # If variance is less than 0.5 for continuous biometric data, it's highly suspicious
    if variance == 0:
        return 100.0  # Mathematically impossible for a living human over time
    elif variance < 0.5:
        return 80.0
    elif variance < 1.0:
        return 40.0
    return 0.0

def _check_autocorrelation(vals: np.ndarray) -> float:
    """
    Real time-series biological data has natural autocorrelation 
    (your heart rate at minute 2 is highly correlated with minute 1).
    Randomly fabricated data lacks this smooth transition.
    """
    if len(vals) < 10:
        return 0.0
        
    # Calculate Lag-1 Autocorrelation
    mean = np.mean(vals)
    var = np.var(vals)
    
    if var == 0:
        return 100.0 # Handled by noise floor, but flatlines are fake
        
    lag1_autocorr = np.sum((vals[:-1] - mean) * (vals[1:] - mean)) / ((len(vals) - 1) * var)
    
    # Biometrics usually have high positive autocorrelation (>0.6)
    # If it's near 0, the numbers are jumping around randomly (human typing)
    if lag1_autocorr < 0.1:
        return 90.0
    elif lag1_autocorr < 0.3:
        return 60.0
    elif lag1_autocorr < 0.5:
        return 30.0
    return 0.0

def _check_integer_clustering(vals: np.ndarray) -> float:
    """
    Sensors output high-precision floats or highly varied integers.
    Humans type round numbers.
    """
    if len(vals) < 5:
        return 0.0
        
    # Count how many values are exact integers (e.g., 72.0 instead of 72.4)
    exact_ints = sum(1 for v in vals if float(v).is_integer())
    ratio = exact_ints / len(vals)
    
    # If it's a metric that should have decimals (like SpO2 or temperature)
    # and it's 100% integers, it's highly suspicious.
    if ratio > 0.95:
        return 85.0
    elif ratio > 0.80:
        return 50.0
    return 0.0


def authenticate_wearable_data(df: pl.DataFrame, patient_col: str, time_col: str, telemetry_cols: list[str]) -> dict:
    """
    Processes time-series wearable data to generate a Sensor Authenticity Score (SAS)
    per patient.
    """
    logger.info("Initializing WearableGate Sensor Authentication...")
    authenticity_reports = {}
    
    try:
        pandas_df = df.to_pandas()
        
        # Ensure temporal ordering
        pandas_df[time_col] = pd.to_datetime(pandas_df[time_col], errors='coerce')
        pandas_df = pandas_df.dropna(subset=[time_col, patient_col])
        
        if pandas_df.empty:
            return authenticity_reports
            
        grouped = pandas_df.groupby(patient_col)
        
        for patient, group_df in grouped:
            if len(group_df) < 10:
                continue # Need a decent time-series window
                
            group_df = group_df.sort_values(by=time_col)
            patient_flags = []
            cumulative_risk = 0.0
            
            for metric in telemetry_cols:
                if metric not in group_df.columns:
                    continue
                    
                vals = group_df[metric].dropna().values
                if len(vals) < 10:
                    continue
                    
                # Run the 3 Hardware vs Human Tests
                noise_risk = _check_noise_floor(vals)
                auto_risk = _check_autocorrelation(vals)
                int_risk = _check_integer_clustering(vals)
                
                metric_risk = max(noise_risk, auto_risk, int_risk)
                
                if metric_risk > 50.0:
                    cumulative_risk += metric_risk
                    
                    reasons = []
                    if noise_risk > 50: reasons.append("Missing Biological Noise Floor")
                    if auto_risk > 50: reasons.append("Failed Autocorrelation (Random Jumps)")
                    if int_risk > 50: reasons.append("Human Integer Clustering")
                    
                    patient_flags.append({
                        "metric": metric,
                        "risk_score": metric_risk,
                        "failure_reasons": reasons
                    })
                    
            if patient_flags:
                # Sensor Authenticity Score (SAS) - Inverted so 0 is fake, 100 is real
                # But here we calculate Risk (0 = Real, 100 = Fake) to match FRI
                sas_risk = min(cumulative_risk / len(telemetry_cols), 100.0)
                
                if sas_risk > 40.0:
                    authenticity_reports[str(patient)] = {
                        "wearable_fabrication_risk": round(sas_risk, 1),
                        "flagged_telemetry": patient_flags,
                        "warning": "Data signatures indicate high probability of manual entry. Hardware sensor authenticity unverified."
                    }
                    
        logger.info(f"WearableGate complete. Flagged {len(authenticity_reports)} patients with suspicious telemetry signatures.")
        return authenticity_reports

    except Exception as e:
        logger.warning(f"WearableGate engine failed: {e}")
        return {}