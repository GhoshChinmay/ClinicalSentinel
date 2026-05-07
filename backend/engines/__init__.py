"""
ClinicalSentinel — Engines Package
Re-exports all engine functions for convenient imports from main.py.
Covers the 7-layer Fabrication Fingerprint Detection (FFD) pipeline.
"""

# ── Core DataSentinel Pipeline ─────────────────────────────────────────────────
from engines.detection import process_and_detect
from engines.cleaning import clean_dataset
from engines.visualization import get_viz_data
from engines.insights import generate_insights
from engines.query import execute_natural_query_stream, confirm_and_execute_edit
from engines.quality import generate_quality_report
from engines.pii_scanner import scan_for_pii, pseudonymise_columns

# ── F1: X-FRI Explainability Layer ────────────────────────────────────────────
from engines.xfri_explainer import decompose_shap_to_layers

# ── F2: GNN Collusion Detector ────────────────────────────────────────────────
from engines.gnn_collusion import detect_collusion_networks, GNN_AVAILABLE

# ── F3: WearableGate Sensor Authenticator ─────────────────────────────────────
from engines.wearable_gate import authenticate_wearable_data

# ── F4: RegRAG Regulatory Compliance Engine ───────────────────────────────────
from engines.reg_rag import evaluate_compliance, initialize_regulatory_knowledge_base

# ── F5: CohortDrift Temporal Drift Detector ───────────────────────────────────
from engines.cohort_drift import detect_cohort_drift

# ── F6: SynthAudit Synthetic Reference Baseline ───────────────────────────────
from engines.synth_audit import audit_against_synthetic

# ── F7: InvestiProfile Behavioral Fingerprinting ──────────────────────────────
from engines.investi_profile import detect_behavioral_anomalies

# ── FRI Composite Scoring Engine ──────────────────────────────────────────────
from engines.fri_calculator import calculate_composite_fri, calculate_fri_report

# ── Reporting Engine ────────────────────────────────────────────────────────
from engines.pdf_report import generate_21cfr_pdf

__all__ = [
    # Core pipeline
    "process_and_detect",
    "clean_dataset",
    "get_viz_data",
    "generate_insights",
    "execute_natural_query_stream",
    "confirm_and_execute_edit",
    "generate_quality_report",
    "scan_for_pii",
    "pseudonymise_columns",
    # F1–F7
    "decompose_shap_to_layers",
    "detect_collusion_networks",
    "GNN_AVAILABLE",
    "authenticate_wearable_data",
    "evaluate_compliance",
    "initialize_regulatory_knowledge_base",
    "detect_cohort_drift",
    "audit_against_synthetic",
    "detect_behavioral_anomalies",
    # FRI
    "calculate_composite_fri",
    "calculate_fri_report",
    "generate_21cfr_pdf"
]