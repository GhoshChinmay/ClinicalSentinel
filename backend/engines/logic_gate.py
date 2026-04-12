"""
DataSentinel — Dynamic Neuro-Symbolic Logic Gate
Uses Groq Cloud LLM to dynamically generate dataset-specific business rules
on the fly, evaluating them safely via Polars expressions.
"""

import os
import json
import polars as pl
from utils import logger


def _generate_dynamic_rules(df: pl.DataFrame) -> list:
    """Ask the AI to generate business rules based purely on the schema."""

    # Build a privacy-safe schema summary
    schema_info = []
    for col, dtype in zip(df.columns, df.dtypes):
        schema_info.append(f"- {col} (Type: {dtype})")
    schema_str = "\n".join(schema_info)

    prompt = f"""You are an expert Data Quality Steward. 
Given the following dataset schema, generate up to 5 STRICT, universally true business logic rules to catch impossible or invalid data. 
Focus ONLY on obvious errors based on the column names (e.g., ages/prices cannot be negative, IDs cannot be missing).

Schema:
{schema_str}

Respond STRICTLY with a JSON object in this exact format. Do NOT include markdown blocks:
{{
    "rules": [
        {{"column": "Age", "operator": "less_than", "value": 0, "reason": "Age cannot be negative"}},
        {{"column": "Patient_ID", "operator": "is_null", "value": null, "reason": "ID cannot be missing"}}
    ]
}}

Supported operators: "less_than", "greater_than", "is_null".
CRITICAL RULES:
1. Only apply rules to columns that actually exist in the schema.
2. Ensure values match the data types (e.g., do not use "less_than" on a string column).
"""
    from groq_client import groq_chat_json

    try:
        messages = [{"role": "user", "content": prompt}]
        data = groq_chat_json(messages, model="llama-3.1-8b-instant", temperature=0.1)

        if not data:
            return []

        rules = data.get("rules", [])
        logger.info(f"AI generated {len(rules)} dynamic logic rules.")

        # --- ADD THESE TWO LINES ---
        for r in rules:
            logger.info(
                f"Dynamic Rule: {r['column']} {r['operator']} {r['value']} ({r['reason']})"
            )
        # ---------------------------

        return rules

    except Exception as e:
        logger.warning(f"Dynamic Logic Gate generation failed: {e}")
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
                condition = pl.col(col) < val
            elif op == "greater_than" and val is not None:
                condition = pl.col(col) > val
            elif op == "is_null":
                condition = pl.col(col).is_null()

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
            logger.warning(f"Failed to apply dynamic rule '{rule}': {e}")

    return df, applied_rules
