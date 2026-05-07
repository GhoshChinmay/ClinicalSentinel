"""
ClinicalSentinel Forensic Math Toolkit
This module contains the statistical tests used to detect human data fabrication.
Layers Implemented:
- Layer 1: Benford's Law (First-digit distribution Chi-Squared test)
- Layer 4: Round-Number Preference (0 and 5 clustering)
- Layer 5: Last-Digit Entropy (Shannon Entropy of terminal digits)
"""

import numpy as np
import pandas as pd
from scipy import stats
import logging

logger = logging.getLogger(__name__)

# Expected Benford's Law distribution for digits 1 through 9
BENFORD_EXPECTED = np.array([np.log10(1 + 1/d) for d in range(1, 10)])

def _extract_first_digit(val):
    """Extracts the first non-zero digit from a number."""
    try:
        num = abs(float(val))
        if num == 0 or np.isnan(num):
            return None
        # Convert to scientific notation to easily grab the first digit regardless of decimals
        s = f"{num:e}"
        return int(s[0])
    except (ValueError, TypeError):
        return None

def _extract_last_digit(val):
    """Extracts the last entered digit (ignoring trailing structural zeros if possible)."""
    try:
        num = abs(float(val))
        if np.isnan(num):
            return None
        # For clinical data (like BP 120, Weight 75.4), we take the last non-decimal character
        # Strip trailing zeros after a decimal point, then grab the last char
        s = str(num).rstrip('0').rstrip('.')
        if not s:
            return 0
        return int(s[-1])
    except (ValueError, TypeError, IndexError):
        return None


def calculate_benfords_law_score(series: pd.Series, min_samples: int = 30) -> dict:
    """
    LAYER 1: Benford's Law Test
    Calculates the Chi-Squared goodness-of-fit against Benford's ideal distribution.
    Returns a dictionary with the p-value and a risk score (0 to 100).
    """
    digits = series.apply(_extract_first_digit).dropna().astype(int)
    
    if len(digits) < min_samples:
        return {"p_value": 1.0, "chi_square": 0.0, "risk_score": 0.0, "valid_samples": len(digits)}

    # Count occurrences of 1-9
    counts = digits.value_counts().reindex(range(1, 10), fill_value=0)
    observed_freq = counts.values
    
    # Calculate expected frequencies
    expected_freq = BENFORD_EXPECTED * len(digits)
    
    # Chi-Squared test
    try:
        chi2_stat, p_value = stats.chisquare(f_obs=observed_freq, f_exp=expected_freq)
        
        # Convert p-value to a Risk Score (Lower p-value = Higher risk of fabrication)
        # If p < 0.05, it statistically violates Benford's Law.
        risk_score = 0.0
        if p_value < 0.01:
            risk_score = 100.0
        elif p_value < 0.05:
            risk_score = 75.0
        elif p_value < 0.10:
            risk_score = 40.0
            
        return {
            "p_value": round(p_value, 5), 
            "chi_square": round(chi2_stat, 2), 
            "risk_score": risk_score,
            "valid_samples": len(digits)
        }
    except Exception as e:
        logger.warning(f"Benford's Law calculation failed: {e}")
        return {"p_value": 1.0, "chi_square": 0.0, "risk_score": 0.0, "valid_samples": len(digits)}


def calculate_round_number_risk(series: pd.Series, min_samples: int = 20) -> dict:
    """
    LAYER 4: Round-Number Preference
    Humans unconsciously favor numbers ending in 0 or 5. 
    In random natural clinical data, this should happen ~20% of the time.
    """
    last_digits = series.apply(_extract_last_digit).dropna().astype(int)
    
    if len(last_digits) < min_samples:
        return {"round_ratio": 0.0, "risk_score": 0.0}

    # Count how many end in 0 or 5
    round_count = last_digits.isin([0, 5]).sum()
    total_count = len(last_digits)
    ratio = round_count / total_count
    
    # Expected is ~0.20. If a doctor enters 0 or 5 over 40% of the time, it's highly suspicious.
    risk_score = 0.0
    if ratio > 0.50:
        risk_score = 100.0
    elif ratio > 0.40:
        risk_score = 70.0
    elif ratio > 0.30:
        risk_score = 30.0

    return {
        "round_ratio": round(ratio, 3),
        "risk_score": risk_score
    }


def calculate_last_digit_entropy(series: pd.Series, min_samples: int = 20) -> dict:
    """
    LAYER 5: Last-Digit Entropy
    Fabricators unconsciously avoid odd numbers like 3, 7, 9. 
    Natural data should have high entropy (even distribution of 0-9).
    """
    last_digits = series.apply(_extract_last_digit).dropna().astype(int)
    
    if len(last_digits) < min_samples:
        return {"entropy": 3.32, "risk_score": 0.0} # 3.32 is max entropy for 10 digits

    counts = last_digits.value_counts(normalize=True).values
    
    # Shannon Entropy formula: -sum(p * log2(p))
    entropy = stats.entropy(counts, base=2)
    
    # Max entropy is log2(10) ≈ 3.32. Lower entropy means highly skewed/fabricated.
    risk_score = 0.0
    if entropy < 2.5:
        risk_score = 100.0
    elif entropy < 2.8:
        risk_score = 65.0
    elif entropy < 3.0:
        risk_score = 30.0

    return {
        "entropy": round(entropy, 3),
        "risk_score": risk_score
    }