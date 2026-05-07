"""
ClinicalSentinel — PII Scanner & Pseudonymization Engine
Strict HIPAA (US) and DPDP Act 2023 (India) compliance layer.
Cryptographically hashes Protected Health Information (PHI) and Medical Identifiers
using SHA-256 before forensic analysis begins.
"""

import re
import os
import hashlib
import polars as pl
from utils import logger

# Enterprise-grade security: Salt prevents rainbow-table attacks on medical IDs
_PII_SALT = os.getenv("CLINICAL_PII_SALT", "ClinicalSentinel_DPDP_HIPAA_Secure_Vault")

# ── CLINICAL PATTERN LIBRARY ─────────────────────────────────────────────────
_NAME_KEYWORDS = {
    "name", "firstname", "lastname", "fullname", "username", 
    "patient_name", "investigator_name", "subject_name", "employee",
}

_CONTACT_KEYWORDS = {
    "email", "phone", "mobile", "tel", "fax", "address", 
    "street", "city", "zip", "postcode", "contact",
}

_CLINICAL_ID_KEYWORDS = {
    "ssn", "national_id", "passport", "dob", "birth", "gender", 
    "sex", "race", "aadhar", "aadhaar", "pan_card", "mrn", "patient_id", 
    "subject_id", "medicare", "medicaid", "insurance"
}

_FINANCIAL_KEYWORDS = {
    "account", "card", "iban", "swift", "bic", "credit", "debit", "salary", "wage"
}

_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_REGEX = re.compile(r"\+?[\d\s\-().]{7,15}")
_SSN_REGEX = re.compile(r"\b\d{3}[-–]\d{2}[-–]\d{4}\b")
_CARD_REGEX = re.compile(r"\b(?:\d[ \-]?){13,19}\b")
_IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

# DPDP Act 2023 / Clinical specifics
_AADHAAR_REGEX = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
_PAN_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b")
_MRN_REGEX = re.compile(r"\b(?:MRN|Patient[-_]?ID)\s*[:#\-]?\s*[A-Z0-9]{5,15}\b", re.IGNORECASE)


def _col_matches_keywords(col: str, keywords: set) -> bool:
    col_lower = col.lower().replace(" ", "_").replace("-", "_")
    return any(kw in col_lower for kw in keywords)


def scan_for_pii(df: pl.DataFrame) -> list[dict]:
    """Scans structural metadata and samples textual data for PHI/PII signatures."""
    findings = []

    for col, dtype in zip(df.columns, df.dtypes):
        # ── Column Name Heuristics ────────────────────────────────────────
        if _col_matches_keywords(col, _NAME_KEYWORDS):
            findings.append({"column": col, "pii_type": "Identity / Name", "confidence": "high", "sample_value": None})
            continue

        if _col_matches_keywords(col, _CONTACT_KEYWORDS):
            findings.append({"column": col, "pii_type": "Contact Information", "confidence": "high", "sample_value": None})
            continue

        if _col_matches_keywords(col, _CLINICAL_ID_KEYWORDS):
            findings.append({"column": col, "pii_type": "Protected Health Info / Govt ID", "confidence": "high", "sample_value": None})
            continue

        if _col_matches_keywords(col, _FINANCIAL_KEYWORDS):
            findings.append({"column": col, "pii_type": "Financial Data", "confidence": "high", "sample_value": None})
            continue

        # ── Value-Level Regex Sampling (Text columns only) ────────────────
        if str(dtype) in ["Utf8", "String"]:
            sample = df[col].drop_nulls().head(50).to_list()

            email_hits = sum(1 for v in sample if _EMAIL_REGEX.search(str(v)))
            ssn_hits = sum(1 for v in sample if _SSN_REGEX.search(str(v)))
            card_hits = sum(1 for v in sample if _CARD_REGEX.search(str(v)))
            phone_hits = sum(1 for v in sample if _PHONE_REGEX.search(str(v)))
            ip_hits = sum(1 for v in sample if _IP_REGEX.search(str(v)))
            aadhaar_hits = sum(1 for v in sample if _AADHAAR_REGEX.search(str(v)))
            pan_hits = sum(1 for v in sample if _PAN_REGEX.search(str(v)))
            mrn_hits = sum(1 for v in sample if _MRN_REGEX.search(str(v)))

            n = max(len(sample), 1)

            # Prioritize highly sensitive IDs first to ensure proper redaction
            if aadhaar_hits > 0:
                findings.append({"column": col, "pii_type": "Aadhaar / National ID", "confidence": "high", "sample_value": "[Aadhaar Redacted]"})
            elif pan_hits > 0:
                findings.append({"column": col, "pii_type": "PAN Card", "confidence": "high", "sample_value": "[PAN Redacted]"})
            elif mrn_hits > 0:
                findings.append({"column": col, "pii_type": "Medical Record Number (MRN)", "confidence": "high", "sample_value": "[MRN Redacted]"})
            elif ssn_hits > 0:
                findings.append({"column": col, "pii_type": "Social Security Number", "confidence": "high", "sample_value": "[SSN Redacted]"})
            elif card_hits > 0:
                findings.append({"column": col, "pii_type": "Payment Card Number", "confidence": "high", "sample_value": "[Card Redacted]"})
            elif email_hits / n > 0.3:
                findings.append({"column": col, "pii_type": "Email Address", "confidence": "high", "sample_value": str(sample[0])[:30] + "..." if sample else None})
            elif phone_hits / n > 0.3:
                findings.append({"column": col, "pii_type": "Phone Number", "confidence": "medium", "sample_value": str(sample[0])[:20] if sample else None})
            elif ip_hits / n > 0.2:
                findings.append({"column": col, "pii_type": "IP Address", "confidence": "medium", "sample_value": str(sample[0])[:20] if sample else None})

    logger.info("Clinical PII Scanner completed. Found %d potential PHI columns.", len(findings))
    return findings


def pseudonymise_columns(df: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
    """Applies Salted SHA-256 hashing to targeted PHI/PII columns for DPDP/HIPAA compliance."""
    for col in columns:
        if col not in df.columns:
            continue

        # Salted hash ensures identical values map to identical hashes (preserving relationships for ML),
        # but protects against reverse-engineering via rainbow tables. We slice the hash to 12 chars 
        # and prefix it to maintain table readability while ensuring cryptographic safety.
        df = df.with_columns(
            pl.col(col)
            .cast(pl.Utf8)
            .map_elements(
                lambda v: (
                    f"SECURE_{hashlib.sha256((_PII_SALT + str(v)).encode()).hexdigest()[:12]}"
                    if v is not None
                    else None
                ),
                return_dtype=pl.Utf8,
            )
            .alias(col)
        )

    logger.info("Pseudonymised %d columns successfully.", len(columns))
    return df