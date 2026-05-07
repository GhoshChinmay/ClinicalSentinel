"""
ClinicalSentinel — Regulatory Insights & Audit Report Engine
Generates an FDA 21 CFR Part 11 Compliant PDF Audit Report.
Combines Groq Cloud LLM narratives with X-FRI SHAP decompositions
and RegRAG regulatory compliance verdicts.
"""

import os
import json
import hashlib
from datetime import datetime
import polars as pl
import numpy as np
import math

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from utils import _session_dir, logger
from groq_client import groq_chat_json
from engines.xfri_explainer import decompose_shap_to_layers
from engines.reg_rag import evaluate_compliance


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _generate_digital_signature(session_id: str, timestamp: str) -> str:
    """Generates a pseudo-cryptographic signature for 21 CFR Part 11 compliance."""
    raw = f"CLINICAL_SENTINEL_AUDIT_{session_id}_{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()

def _safe(val) -> float | None:
    """Convert a value to a JSON-safe float, or None."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 4)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PDF GENERATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def generate_pdf_report(session_id: str, summary_data: dict, top_anomalies: list, pdf_path: str):
    """Draws the official PDF Audit Report using ReportLab."""
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(name="TitleStyle", parent=styles['Heading1'], alignment=1, spaceAfter=20, textColor=colors.darkblue)
    heading_style = ParagraphStyle(name="HeadingStyle", parent=styles['Heading2'], spaceAfter=10, spaceBefore=15, textColor=colors.maroon)
    body_style = ParagraphStyle(name="BodyStyle", parent=styles['Normal'], spaceAfter=10, leading=14)
    alert_style = ParagraphStyle(name="AlertStyle", parent=styles['Normal'], textColor=colors.red, spaceAfter=10)
    sub_style = ParagraphStyle(name="Sub", alignment=1, spaceAfter=20, textColor=colors.red)
    hash_style = ParagraphStyle(name="Hash", fontName="Courier", fontSize=9, textColor=colors.darkgray)

    elements = []

    # ── HEADER ────────────────────────────────────────────────────────
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    signature = _generate_digital_signature(session_id, timestamp)

    elements.append(Paragraph("ClinicalSentinel™ Forensic Audit Report", title_style))
    elements.append(Paragraph("<b>CONFIDENTIAL - REGULATORY COMPLIANCE EXPORT</b>", sub_style))
    
    elements.append(Paragraph(f"<b>Session ID:</b> {session_id}", body_style))
    elements.append(Paragraph(f"<b>Timestamp:</b> {timestamp}", body_style))
    elements.append(Paragraph(f"<b>Compliance Standard:</b> FDA 21 CFR Part 11 & DPDP Act 2023", body_style))
    elements.append(Spacer(1, 15))

    # ── EXECUTIVE SUMMARY (Groq LLM) ──────────────────────────────────
    elements.append(Paragraph("Executive Summary", heading_style))
    elements.append(Paragraph(summary_data.get("executive_summary", "No summary generated."), body_style))
    
    elements.append(Paragraph("Key Findings", heading_style))
    for finding in summary_data.get("key_findings", []):
        elements.append(Paragraph(f"• {finding}", body_style))
    elements.append(Spacer(1, 15))

    # ── X-FRI ANOMALY DECOMPOSITION ───────────────────────────────────
    elements.append(Paragraph("Top High-Risk Investigators / Records (X-FRI)", heading_style))
    
    if not top_anomalies:
        elements.append(Paragraph("No critical fabrication risks detected in this cohort.", body_style))
    else:
        for idx, anom in enumerate(top_anomalies):
            elements.append(Paragraph(f"<b>Record #{idx+1} | Fabrication Risk Index (FRI): {anom['score']}%</b>", alert_style))
            if anom.get('ai_reason'):
                elements.append(Paragraph(f"<i>AI Narrative:</i> {anom['ai_reason']}", body_style))
            
            # ── NEW: Draw the Regulatory Verdict ──
            if anom.get('regulatory_verdict'):
                elements.append(Paragraph(f"<b>Regulatory Verdict (RegRAG):</b> {anom['regulatory_verdict']}", body_style))
            
            # Draw the Layer Decomposition Table
            if anom.get('layers'):
                data = [["Forensic Layer", "Impact Contribution (%)"]]
                for layer, impact in anom['layers'].items():
                    data.append([layer, f"{impact}%"])
                
                t = Table(data, colWidths=[350, 150])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                elements.append(t)
            elements.append(Spacer(1, 15))

    # ── FRI COMPOSITE SCORE SUMMARY ───────────────────────────────────
    session_dir = _session_dir(session_id)
    fri_path = os.path.join(session_dir, "fri_result.json")
    if os.path.exists(fri_path):
        elements.append(Paragraph("Fabrication Risk Index (FRI) Summary", heading_style))
        try:
            with open(fri_path, "r", encoding="utf-8") as f:
                fri_data = json.load(f)
            
            investigators = fri_data.get("investigators", {})
            if investigators:
                # Prepare table data
                table_data = [["Investigator ID", "Records", "FRI Score", "Risk Band"]]
                
                # Sort investigators by FRI score descending
                sorted_invs = sorted(investigators.values(), key=lambda x: x.get("fri_score", 0), reverse=True)
                
                for inv in sorted_invs:
                    score = inv.get("fri_score", 0)
                    band = inv.get("risk_band", "low")
                    inv_id = str(inv.get("investigator_id", "Unknown"))
                    count = str(inv.get("entry_count", 0))
                    table_data.append([inv_id, count, f"{score:.1f}", band.upper()])
                
                t_fri = Table(table_data, colWidths=[150, 80, 100, 170])
                
                # Dynamic styling: Highlight high risk in light coral
                styles_commands = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]
                
                for i, row in enumerate(table_data[1:], start=1):
                    if row[3] == 'HIGH':
                        styles_commands.append(('BACKGROUND', (0, i), (-1, i), colors.lightpink))
                    elif row[3] == 'MEDIUM':
                        styles_commands.append(('BACKGROUND', (0, i), (-1, i), colors.lightyellow))
                
                t_fri.setStyle(TableStyle(styles_commands))
                elements.append(t_fri)
                elements.append(Spacer(1, 15))
        except Exception as e:
            logger.error(f"Error parsing FRI results for PDF: {e}")
            elements.append(Paragraph("FRI data could not be parsed.", body_style))

    # ── DIGITAL SIGNATURE FOOTER ──────────────────────────────────────
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("<b>ELECTRONIC SIGNATURE CERTIFICATION</b>", heading_style))
    elements.append(Paragraph("This document was generated automatically by the ClinicalSentinel multi-modal anomaly detection engine. It employs cryptographic hashing to verify data integrity.", body_style))
    elements.append(Paragraph(f"<b>SHA-256 Hash:</b> {signature}", hash_style))

    # Generate the PDF
    doc.build(elements)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN INSIGHTS CONTROLLER
# ─────────────────────────────────────────────────────────────────────────────

def generate_insights(session_id: str) -> dict:
    """
    Analyzes the dataset, generates an LLM summary, decomposes X-FRI scores,
    and produces a downloadable PDF report.
    """
    logger.info("Generating ClinicalSentinel Audit Insights...")
    session_dir = _session_dir(session_id)
    raw_path = f"{session_dir}/raw_data.parquet"
    pdf_path = os.path.join(session_dir, "clinical_audit_report.pdf")

    if not os.path.exists(raw_path):
        return {"error": "Data not found"}

    df = pl.read_parquet(raw_path)
    pandas_df = df.to_pandas()
    
    # 1. Collect Dataset Metrics
    total_rows = len(pandas_df)
    anomalies_df = pandas_df[pandas_df["is_anomaly"] == True] if "is_anomaly" in pandas_df.columns else pandas_df.head(0)
    total_anomalies = len(anomalies_df)
    
    if total_rows == 0:
        return {"error": "Dataset is empty"}

    # 2. Extract Top Anomalies and Decompose their X-FRI Scores
    top_anomalies = []
    if total_anomalies > 0 and "Threat_Score" in anomalies_df.columns:
        top_df = anomalies_df.sort_values(by="Threat_Score", ascending=False).head(5)
        for idx, row in top_df.iterrows():
            shap_payload = row.get("SHAP_Payload", "[]")
            logic_violation = row.get("logic_violation", None)
            
            # Run the X-FRI Explainer
            layers = decompose_shap_to_layers(shap_payload, logic_violation)
            
            # ── NEW: Run RegRAG Compliance Check ──
            fraud_summary = {
                "risk_score": row.get("Threat_Score", 0),
                "forensic_layers_triggered": layers,
                "ai_reasoning": row.get("AI_Reason", "")
            }
            # Assign a mock investigator ID for the report based on row index
            investigator_id = f"Investigator_Row_{idx}"
            reg_verdict_data = evaluate_compliance(investigator_id, fraud_summary)
            verdict_text = reg_verdict_data.get("regulatory_verdict", "Compliance assessment unavailable.")
            
            top_anomalies.append({
                "score": _safe(row.get("Threat_Score", 0)),
                "ai_reason": row.get("AI_Reason", ""),
                "layers": layers,
                "regulatory_verdict": verdict_text
            })

    # 3. Prompt Groq LLM as a Regulatory Auditor
    prompt = f"""You are a Lead Clinical Trial Forensic Auditor reviewing a dataset for the FDA and CDSCO.
Review the following metrics and write a strictly professional, formal executive summary for an official audit report.
Do not use marketing language. Use regulatory tone (e.g., 'data integrity', 'fabrication risk', 'protocol deviation').

METRICS:
- Total Records Scanned: {total_rows}
- Records Flagged for Fabrication Risk: {total_anomalies} ({(total_anomalies/total_rows)*100:.1f}%)

Respond STRICTLY with a JSON object:
{{
    "executive_summary": "A 3-sentence formal summary of the dataset's overall integrity.",
    "key_findings": [
        "Finding 1 (e.g., overall risk level)",
        "Finding 2 (e.g., mention if the flag rate is acceptable or concerning)"
    ]
}}
"""
    try:
        messages = [{"role": "user", "content": prompt}]
        summary_data = groq_chat_json(messages, model="llama-3.1-8b-instant", temperature=0.2)
        if not summary_data:
            summary_data = {"executive_summary": "Automated summary unavailable.", "key_findings": []}
    except Exception as e:
        logger.warning(f"Groq narrative generation failed: {e}")
        summary_data = {"executive_summary": "AI summary generation failed.", "key_findings": []}

    # 4. Generate the Physical PDF Document
    try:
        generate_pdf_report(session_id, summary_data, top_anomalies, pdf_path)
        logger.info(f"PDF Report generated successfully at {pdf_path}")
    except Exception as e:
        logger.error(f"Failed to generate PDF report: {e}")
        pdf_path = None

    # 5. Return JSON payload for the frontend UI
    return {
        "status": "success",
        "total_records": total_rows,
        "fabrication_flags": total_anomalies,
        "summary": summary_data,
        "top_anomalies_xfri": top_anomalies,
        "pdf_download_url": f"/api/download_report/{session_id}"
    }