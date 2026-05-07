"""
ClinicalSentinel — Cross-Site Copy-Paste Detector (Feature F3/Layer 3)
Implements MinHash Local Sensitive Hashing (LSH) to detect when investigators
copy-paste patient data from other sites or patients, slightly modifying
values to avoid exact-match detection.
"""

import pandas as pd
import numpy as np
import polars as pl
from datasketch import MinHash, MinHashLSH
from utils import logger

def detect_crosssite_copypaste(df: pl.DataFrame, investigator_col: str, metric_cols: list[str]) -> dict:
    """
    Finds duplicated or highly similar patient records across different investigators
    using MinHash LSH. Returns a dictionary of risk scores per investigator.
    """
    logger.info("Initializing MinHash LSH Cross-Site Copy-Paste Detection...")
    
    pandas_df = df.to_pandas()
    
    if investigator_col not in pandas_df.columns:
        logger.warning(f"Investigator column '{investigator_col}' not found.")
        return {}

    # We need a unique identifier for each row (patient/record)
    if "record_id" in pandas_df.columns:
        id_col = "record_id"
    elif "patient_id" in pandas_df.columns:
        id_col = "patient_id"
    else:
        # Fallback to index
        pandas_df["_row_id"] = pandas_df.index
        id_col = "_row_id"
        
    target_metrics = [c for c in metric_cols if c in pandas_df.columns]
    
    if not target_metrics:
        logger.warning("No metrics available for MinHash LSH.")
        return {}
        
    # Prepare MinHash LSH with Jaccard similarity threshold of 0.85 (85% similar)
    lsh = MinHashLSH(threshold=0.85, num_perm=128)
    minhashes = {}
    
    # 1. Create a MinHash for each record based on its clinical values
    for idx, row in pandas_df.iterrows():
        m = MinHash(num_perm=128)
        # Create "tokens" from the metrics. e.g., "HeartRate: 75.5"
        for col in target_metrics:
            val = row[col]
            if pd.notna(val):
                # Round to 1 decimal to allow slight perturbations
                if isinstance(val, (int, float)):
                    token = f"{col}:{round(float(val), 1)}"
                else:
                    token = f"{col}:{val}"
                m.update(token.encode('utf8'))
        
        record_id = str(row[id_col])
        minhashes[record_id] = m
        lsh.insert(record_id, m)
        
    # 2. Query LSH to find copy-pasted records
    copypaste_flags = {}
    record_to_inv = pandas_df.set_index(id_col)[investigator_col].to_dict()
    
    for record_id, m in minhashes.items():
        # Find similar records
        result = lsh.query(m)
        
        # Filter out self
        similar_records = [r for r in result if r != record_id]
        
        if similar_records:
            owner_inv = str(record_to_inv.get(record_id, ""))
            if owner_inv not in copypaste_flags:
                copypaste_flags[owner_inv] = 0
                
            # If the similar record comes from a DIFFERENT investigator, it's higher risk
            for sim_r in similar_records:
                sim_inv = str(record_to_inv.get(sim_r, ""))
                if sim_inv != owner_inv:
                    copypaste_flags[owner_inv] += 5.0 # Cross-site copy paste!
                else:
                    copypaste_flags[owner_inv] += 1.0 # Same-site copy paste
                    
    # 3. Normalize into a 0-100 risk score per investigator
    reports = {}
    grouped = pandas_df.groupby(investigator_col).size()
    
    for inv, count in grouped.items():
        inv_str = str(inv)
        flags = copypaste_flags.get(inv_str, 0)
        
        if flags > 0:
            # Score is based on proportion of copied records, scaled up.
            score = min(100.0, (flags / count) * 100 * 2.0)
            reports[inv_str] = {
                "LSH_copypaste_score": round(score, 1),
                "copypaste_instances": int(flags)
            }
            
    logger.info(f"LSH detection complete. Found {len(reports)} investigators with copy-paste signals.")
    return reports
