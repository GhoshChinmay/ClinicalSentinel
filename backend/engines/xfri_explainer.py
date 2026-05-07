"""
ClinicalSentinel — Explainable Fabrication Risk Index (X-FRI) Explainer
Decomposes an investigator's anomaly score into the 6 specific forensic layers
using SHAP values. Provides regulatory-grade audit trails.
"""

import json

# Define our 6-layer forensic taxonomy
CLINICAL_LAYERS = {
    "LAYER_1_BENFORD": ["_benford_risk"],
    "LAYER_2_TEMPORAL": ["velocity_1h_count", "velocity_24h_sum", "lstm_anomaly_score"],
    "LAYER_3_STATISTICAL": ["_entity_z", "ecod_score", "lof_score"],
    "LAYER_4_ROUND_NUM": ["_round_risk"],
    "LAYER_5_ENTROPY": ["_entropy_risk"],
    "LAYER_6_LOGIC": ["logic_violation"]
}

def decompose_shap_to_layers(shap_payload_str: str, logic_violation: str = None) -> dict:
    """
    Takes a raw SHAP JSON array and maps the feature impacts to the 6 Clinical Layers.
    Outputs a percentage breakdown of why the row was flagged.
    """
    layer_impacts = {
        "Layer 1: Benford's Law (Mathematical Manipulation)": 0.0,
        "Layer 2: Temporal Burst (Bulk Entry)": 0.0,
        "Layer 3: Inter-Site Distribution (Statistical Outlier)": 0.0,
        "Layer 4: Round-Number Preference (Human Fabrication)": 0.0,
        "Layer 5: Last-Digit Entropy (Subconscious Bias)": 0.0,
        "Layer 6: Clinical Plausibility (Biological Reality)": 0.0
    }
    
    total_impact = 0.0
    
    # 1. Handle Hard Logic Violations (Layer 6 Override)
    if logic_violation and isinstance(logic_violation, str) and str(logic_violation).lower() != "nan":
        layer_impacts["Layer 6: Clinical Plausibility (Biological Reality)"] = 100.0
        return layer_impacts
        
    # 2. Parse SHAP Payload
    if not shap_payload_str or shap_payload_str == "[]":
        return layer_impacts
        
    try:
        shap_items = json.loads(shap_payload_str)
        for item in shap_items:
            feature = item.get("feature", "")
            impact = abs(item.get("impact", 0.0))
            
            # Map the feature to its respective layer
            mapped = False
            for layer_name, suffixes in CLINICAL_LAYERS.items():
                if any(suf in feature for suf in suffixes):
                    if "BENFORD" in layer_name:
                        layer_impacts["Layer 1: Benford's Law (Mathematical Manipulation)"] += impact
                    elif "TEMPORAL" in layer_name:
                        layer_impacts["Layer 2: Temporal Burst (Bulk Entry)"] += impact
                    elif "STATISTICAL" in layer_name:
                        layer_impacts["Layer 3: Inter-Site Distribution (Statistical Outlier)"] += impact
                    elif "ROUND" in layer_name:
                        layer_impacts["Layer 4: Round-Number Preference (Human Fabrication)"] += impact
                    elif "ENTROPY" in layer_name:
                        layer_impacts["Layer 5: Last-Digit Entropy (Subconscious Bias)"] += impact
                    mapped = True
                    break
                    
            # If it doesn't match a specific forensic layer, it's a generic statistical outlier (Layer 3)
            if not mapped:
                layer_impacts["Layer 3: Inter-Site Distribution (Statistical Outlier)"] += impact
                
            total_impact += impact
            
    except Exception:
        pass
        
    # Normalize to percentages
    if total_impact > 0:
        for k in layer_impacts:
            layer_impacts[k] = round((layer_impacts[k] / total_impact) * 100, 1)
            
    # Clean up empty layers
    return {k: v for k, v in layer_impacts.items() if v > 0}