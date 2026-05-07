"""
ClinicalSentinel — Dynamic Neuro-Symbolic Logic Gate (Layer 6)
Uses Groq Cloud LLM to dynamically generate dataset-specific physiological 
and clinical plausibility rules on the fly, evaluating them safely via Polars.
"""

import os
import json
import polars as pl
from utils import logger


def _generate_dynamic_rules(df: pl.DataFrame) -> list:
    """Ask the AI to generate clinical plausibility rules based on the schema and sample data."""

    # Build a privacy-safe schema summary with sample values to give context to the LLM
    schema_info = []
    try:
        # Pull 3 sample rows to help the AI understand the clinical data format
        sample_df = df.head(3).to_pandas()
        for col in df.columns:
            dtype = df[col].dtype
            sample_vals = [str(x) for x in sample_df[col].tolist() if x is not None]
            sample_str = ", ".join(sample_vals)
            schema_info.append(f"- {col} (Type: {dtype}, Samples: [{sample_str}])")
    except Exception:
        # Fallback to just schema if sampling fails
        for col, dtype in zip(df.columns, df.dtypes):
            schema_info.append(f"- {col} (Type: {dtype})")

    schema_str = "\n".join(schema_info)

    prompt = f"""You are an expert Clinical Trial Data Manager and Forensic Auditor.
Given the following dataset schema and sample values, generate up to 8 STRICT, universally true physiological plausibility rules or clinical business logic rules to catch impossible, fabricated, or invalid medical data. 
Focus ONLY on obvious clinical errors based on the column names (e.g., Blood Pressure cannot be negative or > 300, Heart Rate cannot exceed 220, Body Temperature cannot be < 30C or > 43C, patient IDs cannot be missing).

Schema:
{schema_str}

Respond STRICTLY with a JSON object in this exact format. Do NOT include markdown blocks:
{{
    "rules": [
        {{"column": "Systolic_BP", "operator": "greater_than", "value": 300, "reason": "Systolic Blood Pressure over 300 is physiologically impossible"}},
        {{"column": "Patient_ID", "operator": "is_null", "value": null, "reason": "Patient ID cannot be missing"}},
        {{"column": "Age", "operator": "not_between", "value": [0, 120], "reason": "Age falls outside the biologically possible human lifespan"}},
        {{"column": "Status", "operator": "contains", "value": "test", "reason": "Test or synthetic data left in the production system"}}
    ]
}}

Supported operators: "less_than", "greater_than", "is_null", "equals", "not_equals", "contains", "regex_match", "between", "not_between".
CRITICAL RULES:
1. Only apply rules to columns that actually exist in the schema.
2. Ensure values match the data types (e.g., do not use "less_than" on a string column).
3. For "between" and "not_between", the value MUST be a list of two numbers: [min, max]. 
   - Use "between" to flag data that falls INSIDE an invalid range.
   - Use "not_between" to flag data that falls OUTSIDE a valid range (e.g., normal HR is 30-220, so use "not_between": [30, 220] to catch anomalies).
4. Focus heavily on clinical plausibility and fabrication red flags.
"""
    from groq_client import groq_chat_json

    try:
        messages = [{"role": "user", "content": prompt}]
        # Llama 3.1 is highly capable of structured clinical reasoning
        data = groq_chat_json(messages, model="llama-3.1-8b-instant", temperature=0.1)

        if not data:
            return []

        rules = data.get("rules", [])
        logger.info("AI generated %d dynamic clinical logic rules.", len(rules))

        for r in rules:
            logger.info(
                "Clinical Rule: %s %s %s (%s)",
                r.get('column'), r.get('operator'), r.get('value'), r.get('reason'),
            )

        return rules

    except Exception as e:
        logger.warning("Dynamic Clinical Logic Gate generation failed: %s", e)
        return []


def apply_logic_gate(df: pl.DataFrame):
    """Safely parse the AI's JSON rules and apply them to the DataFrame."""

    rules = _generate_dynamic_rules(df)
    applied_rules = []

    # Initialize the violation column if it doesn't exist
    if "logic_violation" not in df.columns:
        df = df.with_columns(pl.lit(None).cast(pl.Utf8).alias("logic_violation"))

    for rule in rules:
        col = rule.get("column")
        op = rule.get("operator")
        val = rule.get("value")
        reason = rule.get("reason")

        # Security check: Ensure the AI didn't hallucinate a column
        if not col or col not in df.columns:
            continue

        try:
            # Safely build Polars execution conditions
            condition = None
            if op == "less_than" and val is not None:
                condition = pl.col(col).cast(pl.Float64, strict=False) < float(val)
            elif op == "greater_than" and val is not None:
                condition = pl.col(col).cast(pl.Float64, strict=False) > float(val)
            elif op == "is_null":
                condition = pl.col(col).is_null()
            elif op == "equals" and val is not None:
                if isinstance(val, str):
                    condition = pl.col(col).cast(pl.Utf8) == str(val)
                else:
                    condition = pl.col(col).cast(pl.Float64, strict=False) == float(val)
            elif op == "not_equals" and val is not None:
                if isinstance(val, str):
                    condition = pl.col(col).cast(pl.Utf8) != str(val)
                else:
                    condition = pl.col(col).cast(pl.Float64, strict=False) != float(val)
            elif op == "contains" and val is not None:
                condition = pl.col(col).cast(pl.Utf8).str.contains("(?i)" + str(val)) # Case-insensitive
            elif op == "regex_match" and val is not None:
                condition = pl.col(col).cast(pl.Utf8).str.contains(str(val))
            elif op == "between" and isinstance(val, list) and len(val) == 2:
                condition = pl.col(col).cast(pl.Float64, strict=False).is_between(float(val[0]), float(val[1]))
            elif op == "not_between" and isinstance(val, list) and len(val) == 2:
                condition = ~pl.col(col).cast(pl.Float64, strict=False).is_between(float(val[0]), float(val[1]))

            # Apply the mathematical condition
            if condition is not None:
                df = df.with_columns(
                    pl.when(condition & pl.col("logic_violation").is_null())
                    .then(pl.lit(reason))
                    .when(condition & pl.col("logic_violation").is_not_null())
                    .then(pl.col("logic_violation") + " | " + pl.lit(reason))
                    .otherwise(pl.col("logic_violation"))
                    .alias("logic_violation")
                )
                applied_rules.append(rule)

        except Exception as e:
            logger.warning("Failed to apply clinical rule '%s': %s", rule, e)

    return df, applied_rules