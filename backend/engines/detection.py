"""
DataSentinel — Anomaly Detection Engine
Isolation Forest anomaly detection with Velocity Engine, Threat Scoring,
and Neuro-Symbolic Logic Gating.
"""

import uuid
import polars as pl
import pandas as pd
import numpy as np
import json
from sklearn.ensemble import IsolationForest, HistGradientBoostingClassifier
import shap
import random

from utils import _session_dir, logger
from engines.nlp_bridge import process_text_anomalies
from engines.logic_gate import apply_logic_gate


def process_and_detect(
    file_path: str = None,
    session_id: str = None,
    algorithm: str = "isolation_forest",
    df: pl.DataFrame = None,
):
    """
    Run the full anomaly detection pipeline.
    Accepts either a file_path to read or a pre-loaded DataFrame.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    session_dir = _session_dir(session_id)

    # --- DATA LOADING (skip if DataFrame already provided) ---
    if df is None:
        try:
            df = pl.read_csv(file_path, infer_schema_length=1000000)
        except Exception as primary_err:
            logger.warning(
                "Polars CSV read failed (%s), attempting pandas fallback...",
                primary_err,
            )
            try:
                pandas_fallback = pd.read_csv(file_path, low_memory=False)
                df = pl.from_pandas(pandas_fallback)
            except Exception as inner_e:
                return {
                    "error": f"Fatal Read Error. Both engines failed to parse the CSV: {str(inner_e)}"
                }

    pre_dedup = len(df)
    df = df.unique()
    logger.info("Dedup complete: %d → %d rows.", pre_dedup, len(df))

    # ---------------------------------------------------------
    # STAGE 1: THE NEURO-SYMBOLIC LOGIC GATE (Semantic Context)
    # ---------------------------------------------------------
    df, applied_rules = apply_logic_gate(df)

    # ---------------------------------------------------------
    # STAGE 2: THE VELOCITY ENGINE (Time-Series Context)
    # ---------------------------------------------------------
    time_cols = [
        c
        for c in df.columns
        if "date" in c.lower() or "time" in c.lower() or "timestamp" in c.lower()
    ]
    entity_keywords = [
        "user",
        "account",
        "customer",
        "merchant",
        "employee",
        "sender",
        "client",
        "patient",
    ]
    id_cols = [
        c
        for c in df.columns
        if "id" in c.lower() and any(kw in c.lower() for kw in entity_keywords)
    ]

    velocity_cols_added = []

    if time_cols and id_cols:
        t_col = time_cols[0]
        i_col = id_cols[0]

        logger.info(
            "Time-Series detected. Tracking velocity for '%s' over '%s'...",
            i_col,
            t_col,
        )

        try:
            if df[t_col].dtype not in [pl.Datetime, pl.Date]:
                parsed = None
                datetime_formats = [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d",
                    "%m/%d/%Y %H:%M:%S",
                    "%m/%d/%Y",
                    "%d-%m-%Y %H:%M:%S",
                    "%d/%m/%Y %H:%M:%S",
                ]
                for fmt in datetime_formats:
                    try:
                        parsed = df.with_columns(
                            pl.col(t_col).str.strptime(
                                pl.Datetime, format=fmt, strict=False
                            )
                        )
                        null_pct = parsed[t_col].null_count() / len(parsed)
                        if null_pct < 0.5:
                            df = parsed
                            logger.info("Parsed '%s' with format '%s'.", t_col, fmt)
                            break
                        else:
                            parsed = None
                    except Exception:
                        continue

                if parsed is None:
                    raise ValueError(
                        f"Could not parse '{t_col}' as datetime with any known format."
                    )

            if df[t_col].dtype == pl.Date:
                df = df.with_columns(pl.col(t_col).cast(pl.Datetime))

            df = df.filter(pl.col(t_col).is_not_null())
            df = df.sort([i_col, t_col])

            numeric_cols_for_velocity = [
                c
                for c, d in zip(df.columns, df.dtypes)
                if d in [pl.Float64, pl.Int64, pl.Float32, pl.Int32]
            ]
            amount_keywords = [
                "amount",
                "value",
                "price",
                "total",
                "balance",
                "sum",
                "cost",
                "payment",
            ]
            smart_picks = [
                c
                for c in numeric_cols_for_velocity
                if any(kw in c.lower() for kw in amount_keywords)
            ]
            track_col = (
                smart_picks[0]
                if smart_picks
                else (
                    numeric_cols_for_velocity[0] if numeric_cols_for_velocity else None
                )
            )

            if track_col:
                df = df.with_columns(pl.lit(1).alias("_txn_counter"))
                df = df.with_columns(
                    [
                        pl.col(track_col)
                        .rolling_sum_by(by=t_col, window_size="1d", closed="both")
                        .over(i_col)
                        .alias("velocity_24h_sum"),
                        pl.col("_txn_counter")
                        .rolling_sum_by(by=t_col, window_size="1h", closed="both")
                        .over(i_col)
                        .alias("velocity_1h_count"),
                    ]
                )
                df = df.with_columns(
                    [
                        pl.col("velocity_24h_sum").fill_null(0),
                        pl.col("velocity_1h_count").fill_null(0),
                    ]
                )
                df = df.drop("_txn_counter")
                velocity_cols_added = ["velocity_24h_sum", "velocity_1h_count"]
                logger.info(
                    "Velocity tracking successfully generated for '%s'.", track_col
                )
            else:
                logger.info(
                    "Velocity Engine skipped — no numeric columns found for tracking."
                )
        except Exception as e:
            logger.warning("Velocity Engine skipped due to parsing error: %s", e)

    df = process_text_anomalies(df)
    pandas_df = df.to_pandas()

    numeric_cols = [
        c
        for c in pandas_df.select_dtypes(include=[np.number]).columns.tolist()
        if c not in time_cols
    ]
    cat_cols = pandas_df.select_dtypes(include=["object", "string"]).columns.tolist()

    # Exclude logic_violation from categorical encoding to prevent noise
    if "logic_violation" in cat_cols:
        cat_cols.remove("logic_violation")

    encoded_df = pandas_df[numeric_cols].copy().fillna(0)
    for col in cat_cols:
        freq_encoding = pandas_df[col].value_counts(normalize=True).to_dict()
        encoded_df[col + "_freq"] = pandas_df[col].map(freq_encoding).fillna(0)

    # ---------------------------------------------------------
    # STAGE 3: THE AI DETECTION ENGINE (Isolation Forest)
    # ---------------------------------------------------------
    recommendation = "Isolation Forest (Z-Score Scaled)"

    # BASELINE PROTECTOR: Exclude Neuro-Symbolic violations from training the Isolation Forest!
    clean_encoded_df = encoded_df
    if "logic_violation" in pandas_df.columns:
        clean_encoded_df = encoded_df[pandas_df["logic_violation"].isna()]

    max_if_samples = 50000
    if len(clean_encoded_df) > max_if_samples:
        train_df = clean_encoded_df.sample(n=max_if_samples, random_state=42)
    else:
        train_df = clean_encoded_df

    model_fitted = False
    model = None

    if len(train_df) == 0:
        logger.warning(
            "No clean training data available. Falling back to full dataset."
        )
        train_df = encoded_df

    if len(train_df) > 0:
        model = IsolationForest(n_estimators=100, n_jobs=-1, random_state=42)
        model.fit(train_df)
        raw_scores = model.decision_function(encoded_df)
        inverted_scores = -raw_scores
        mean_weirdness = np.mean(inverted_scores)
        std_weirdness = np.std(inverted_scores)
        threshold = mean_weirdness + (1.5 * std_weirdness)
        model_fitted = True
    else:
        logger.warning("Dataset is entirely empty. Skipping AI anomaly detection.")
        inverted_scores = (
            np.zeros(len(encoded_df)) if len(encoded_df) > 0 else np.array([])
        )
        threshold = 1.0

    # Base Flagging
    is_anomaly = []
    for i, s in enumerate(inverted_scores) if len(inverted_scores) > 0 else []:
        has_logic_error = "logic_violation" in pandas_df.columns and pd.notna(
            pandas_df.at[i, "logic_violation"]
        )
        is_anomaly.append(bool((model_fitted and s > threshold) or has_logic_error))

    # =========================================================
    # THE ANOMALY OVERLOAD SHIELD (NEW FIX)
    # =========================================================

    # 1. SHIELD: Bypass broken logic gate rules
    logic_flags = sum(
        1
        for i in range(len(pandas_df))
        if "logic_violation" in pandas_df.columns
        and pd.notna(pandas_df.at[i, "logic_violation"])
    )
    if len(pandas_df) > 0 and logic_flags / len(pandas_df) > 0.90:
        logger.warning(
            "Logic Gate blocked >90% of rows! Rules are incompatible. Bypassing Logic Gate entirely."
        )
        if "logic_violation" in pandas_df.columns:
            pandas_df["logic_violation"] = np.nan  # Wipe the broken rules
        # Recalculate purely on statistics
        is_anomaly = [
            bool(model_fitted and s > threshold)
            for s in (inverted_scores if len(inverted_scores) > 0 else [])
        ]

    # 2. SHIELD: Cap statistical anomalies to a maximum of 10%
    stat_anomaly_count = sum(
        1
        for i, x in enumerate(is_anomaly)
        if x
        and not (
            "logic_violation" in pandas_df.columns
            and pd.notna(pandas_df.at[i, "logic_violation"])
        )
    )
    if len(pandas_df) > 0 and stat_anomaly_count / len(pandas_df) > 0.10:
        logger.warning("Statistical Anomaly Overload. Forcing a 10% cap.")
        if len(inverted_scores) > 0:
            top_10_threshold = np.percentile(
                inverted_scores, 90
            )  # Find the 90th percentile score
            for i, x in enumerate(is_anomaly):
                # Only un-flag statistical anomalies that didn't make the top 10% cut
                if x and not (
                    "logic_violation" in pandas_df.columns
                    and pd.notna(pandas_df.at[i, "logic_violation"])
                ):
                    if inverted_scores[i] < top_10_threshold:
                        is_anomaly[i] = False

    # Safety check if dataframe was completely empty
    if len(is_anomaly) < len(df):
        is_anomaly.extend([False] * (len(df) - len(is_anomaly)))

    df = df.with_columns(pl.Series(name="is_anomaly", values=is_anomaly))

    # ---------------------------------------------------------
    # STAGE 4: SHAP EXPLAINABILITY LAYER
    # ---------------------------------------------------------
    try:
        shap_payloads = ["[]"] * len(pandas_df)

        # ONLY run SHAP if the model was actually fitted
        if model_fitted and model is not None:
            logger.info("Computing SHAP values for anomaly attribution...")
            explainer = shap.TreeExplainer(model)

            # COMPUTE SAVER: Only run SHAP for statistical anomalies. Logic errors don't need SHAP.
            stat_anomaly_indices = [
                i
                for i, x in enumerate(is_anomaly)
                if x
                and not (
                    "logic_violation" in pandas_df.columns
                    and pd.notna(pandas_df.at[i, "logic_violation"])
                )
            ]

            feature_names = encoded_df.columns.tolist()

            if stat_anomaly_indices:
                anom_encoded_df = encoded_df.iloc[stat_anomaly_indices]
                shap_vals = explainer.shap_values(anom_encoded_df)

                for j, orig_idx in enumerate(stat_anomaly_indices):
                    row_shap = shap_vals[j]
                    top_indices = np.argsort(np.abs(row_shap))[-3:][::-1]

                    contributions = []
                    for idx in top_indices:
                        contributions.append(
                            {
                                "feature": feature_names[idx],
                                "impact": float(row_shap[idx]),
                            }
                        )
                    shap_payloads[orig_idx] = json.dumps(contributions)

        df = df.with_columns(pl.Series(name="SHAP_Payload", values=shap_payloads))
    except Exception as e:
        logger.warning("SHAP attribution failed: %s", e)
        df = df.with_columns(
            pl.Series(name="SHAP_Payload", values=["[]"] * len(pandas_df))
        )

    # ---------------------------------------------------------
    # STAGE 5: TIER 2 THREAT ENGINE (Scoring)
    # ---------------------------------------------------------
    if "Class" in pandas_df.columns:
        try:
            X = (
                encoded_df.drop(columns=["Class"])
                if "Class" in encoded_df.columns
                else encoded_df
            )
            y = pandas_df["Class"].fillna(0)

            max_train_samples = 50000
            if len(X) > max_train_samples:
                sample_idx = np.random.choice(
                    len(X), size=max_train_samples, replace=False
                )
                X_train = X.iloc[sample_idx]
                y_train = y.iloc[sample_idx]
            else:
                X_train = X
                y_train = y

            classifier = HistGradientBoostingClassifier(
                class_weight="balanced", random_state=42
            )
            classifier.fit(X_train, y_train)

            probabilities = classifier.predict_proba(X)[:, 1]
            threat_scores = []
            for i, p in enumerate(probabilities):
                has_logic_error = "logic_violation" in pandas_df.columns and pd.notna(
                    pandas_df.at[i, "logic_violation"]
                )
                threat_scores.append(100.0 if has_logic_error else round(p * 100, 2))

            df = df.with_columns(pl.Series(name="Threat_Score", values=threat_scores))
        except Exception as e:
            logger.warning("Supervised Engine failed: %s", e)
            df = df.with_columns(
                pl.Series(name="Threat_Score", values=[0] * len(pandas_df))
            )
    else:
        try:
            if model_fitted and len(inverted_scores) > 0:
                min_s = inverted_scores.min()
                max_s = inverted_scores.max()
            else:
                min_s, max_s = 0, 0

            threat_scores = []
            if max_s > min_s:
                for i, s in enumerate(inverted_scores):
                    has_logic_error = (
                        "logic_violation" in pandas_df.columns
                        and pd.notna(pandas_df.at[i, "logic_violation"])
                    )

                    if has_logic_error:
                        threat_scores.append(
                            100.0
                        )  # Absolute logical failure = Max threat
                    elif is_anomaly[i]:
                        range_anom = max_s - threshold
                        score = (
                            60 + (((s - threshold) / range_anom) * 40)
                            if range_anom > 0
                            else 100
                        )
                        threat_scores.append(min(100.0, max(0.0, round(score, 2))))
                    else:
                        range_norm = threshold - min_s
                        score = (
                            (((s - min_s) / range_norm) * 40) if range_norm > 0 else 0
                        )
                        threat_scores.append(min(100.0, max(0.0, round(score, 2))))
            else:
                for i in range(len(pandas_df)):
                    has_logic_error = (
                        "logic_violation" in pandas_df.columns
                        and pd.notna(pandas_df.at[i, "logic_violation"])
                    )
                    threat_scores.append(100.0 if has_logic_error else 0.0)

            df = df.with_columns(pl.Series(name="Threat_Score", values=threat_scores))
        except Exception as e:
            logger.warning("Synthetic Engine failed: %s", e)
            df = df.with_columns(
                pl.Series(name="Threat_Score", values=[0] * len(pandas_df))
            )

    # ---------------------------------------------------------
    # STAGE 6: NARRATIVE SYNTHESIS (AI Reason Generator)
    # ---------------------------------------------------------
    logger.info("Starting Narrative Synthesis for AI Reasoning...")

    engineered_suffixes = ("_length", "_digit_ratio", "_upper_ratio", "_special_ratio")
    engineered_prefixes = ("nlp_pc",)
    velocity_col_names = set(velocity_cols_added)

    original_numeric = [
        c
        for c in numeric_cols
        if not c.endswith(engineered_suffixes)
        and not any(c.startswith(p) for p in engineered_prefixes)
        and c not in velocity_col_names
    ]

    reasons_list = [""] * len(pandas_df)

    if any(is_anomaly):
        stats = {}
        for col in original_numeric:
            col_mean = pandas_df[col].mean()
            col_std = pandas_df[col].std()
            stats[col] = {
                "mean": col_mean if pd.notna(col_mean) else 0,
                "std": col_std if pd.notna(col_std) else 0,
            }

        rare_cats = {}
        for col in cat_cols:
            if pandas_df[col].nunique() / len(pandas_df) < 0.3:
                counts = pandas_df[col].value_counts(normalize=True)
                rare_cats[col] = counts[counts < 0.05].index.tolist()

        anomaly_indices = [i for i, x in enumerate(is_anomaly) if x]

        parsed_shap = {}
        if "SHAP_Payload" in df.columns:
            shap_col = df["SHAP_Payload"].to_list()
            for idx in anomaly_indices:
                try:
                    payload = json.loads(shap_col[idx])
                    if payload:
                        parsed_shap[idx] = payload
                except Exception:
                    pass

        for idx in anomaly_indices:
            row = pandas_df.iloc[idx]

            # --- LOGIC GATE OVERRIDE ---
            if "logic_violation" in pandas_df.columns and pd.notna(
                row["logic_violation"]
            ):
                reasons_list[idx] = (
                    f"Semantic Violation (Neuro-Symbolic Gate): {row['logic_violation']}"
                )
                continue

            # --- STANDARD SHAP NARRATIVE ---
            if idx in parsed_shap and len(parsed_shap[idx]) > 0:
                shap_items = parsed_shap[idx]

                top_feat = shap_items[0]["feature"]
                top_impact = shap_items[0]["impact"]

                orig_feat = (
                    top_feat.replace("_freq", "")
                    if top_feat.endswith("_freq")
                    else top_feat
                )
                val = row.get(orig_feat, "Unknown")
                if isinstance(val, float) and pd.notna(val):
                    val = f"{val:.2f}"

                context = ""
                if orig_feat in stats and stats[orig_feat]["std"] > 0:
                    z = (row[orig_feat] - stats[orig_feat]["mean"]) / stats[orig_feat][
                        "std"
                    ]
                    direction = "higher" if z > 0 else "lower"
                    context = f"which is {abs(z):.1f} standard deviations {direction} than the typical average of {stats[orig_feat]['mean']:.2f}"
                elif orig_feat in rare_cats and str(val) in rare_cats[orig_feat]:
                    context = "representing a highly uncommon category in this dataset"
                elif top_feat in velocity_cols_added:
                    context = "indicating an abnormal burst in temporal activity"
                else:
                    context = "deviating significantly from standard patterns"

                primary_templates = [
                    f"The primary anomaly driver is '{orig_feat}' (value: {val}), {context}.",
                    f"This row was flagged heavily due to '{orig_feat}' ({val}), {context}.",
                    f"Model detection heavily weighted '{orig_feat}' ({val}) as anomalous, {context}.",
                    f"An extreme variance in '{orig_feat}' ({val}) triggered the detection, {context}.",
                ]
                reason = random.choice(primary_templates)

                if len(shap_items) > 1 and abs(shap_items[1]["impact"]) > (
                    abs(top_impact) * 0.25
                ):
                    sec_feat = shap_items[1]["feature"]
                    sec_orig = (
                        sec_feat.replace("_freq", "")
                        if sec_feat.endswith("_freq")
                        else sec_feat
                    )
                    sec_val = row.get(sec_orig, "Unknown")
                    if isinstance(sec_val, float) and pd.notna(sec_val):
                        sec_val = f"{sec_val:.2f}"

                    sec_templates = [
                        f" This is compounded by unusual behavior in '{sec_orig}' (value: {sec_val}).",
                        f" Additionally, '{sec_orig}' ({sec_val}) strongly deviates from expectations.",
                        f" The model also found the interaction with '{sec_orig}' ({sec_val}) to be highly irregular.",
                    ]
                    reason += random.choice(sec_templates)

                reasons_list[idx] = reason

            else:
                max_z = 0
                max_col = None
                for col in original_numeric:
                    if stats[col]["std"] > 0:
                        z = abs((row[col] - stats[col]["mean"]) / stats[col]["std"])
                        if z > max_z:
                            max_z, max_col = z, col

                if max_col and max_z > 2.0:
                    reasons_list[idx] = (
                        f"Detected via multivariate analysis: '{max_col}' ({row[max_col]:.2f}) is an extreme outlier ({max_z:.1f}σ) when combined with other fields."
                    )
                else:
                    reasons_list[idx] = (
                        "The AI model detected a complex, multi-dimensional pattern break in this row."
                    )

    df = df.with_columns(pl.Series(name="AI_Reason", values=reasons_list))

    # Clean up the internal logic_violation column before saving so the UI remains pristine
    if "logic_violation" in df.columns:
        df = df.drop("logic_violation")

    raw_parquet_path = f"{session_dir}/raw_data.parquet"
    df.write_parquet(raw_parquet_path)

    # ---------------------------------------------------------
    # STAGE 7: SMART CLEANING RECOMMENDATION ENGINE
    # ---------------------------------------------------------
    col_str = " ".join(df.columns).lower()

    text_heavy = len(cat_cols) >= len(numeric_cols) and len(cat_cols) > 0
    is_large = len(pandas_df) > 2000
    has_time = len(time_cols) > 0

    if text_heavy or any(
        kw in col_str
        for kw in ["review", "text", "description", "summary", "comment", "feedback"]
    ):
        recommended_cleaning = "mask"
        cleaning_rationale = "Text-heavy dataset detected. We recommend 'Masking' to safely redact anomalous strings, typos, or bot-generated text with a [REDACTED] tag without destroying the rest of the row."
    elif any(
        kw in col_str
        for kw in [
            "amount",
            "transaction",
            "fraud",
            "price",
            "payment",
            "bank",
            "credit",
            "merchant",
            "card",
        ]
    ):
        recommended_cleaning = "quarantine"
        cleaning_rationale = "Financial or Security data detected. 'Quarantine' is strictly recommended to isolate threats and anomalies without erasing the forensic evidence."
    elif has_time and any(
        kw in col_str
        for kw in [
            "sensor",
            "temp",
            "reading",
            "humidity",
            "metric",
            "iot",
            "cpu",
            "memory",
            "speed",
        ]
    ):
        recommended_cleaning = "impute"
        cleaning_rationale = "Sequential telemetry/sensor data detected. 'Predictive KNN Imputation' is recommended to smoothly bridge over hardware glitches or dropped signals."
    elif any(
        kw in col_str
        for kw in [
            "age",
            "passenger",
            "survived",
            "income",
            "gender",
            "sex",
            "patient",
            "blood",
            "disease",
            "fare",
        ]
    ):
        recommended_cleaning = "impute"
        cleaning_rationale = "Demographic data detected. 'Contextual Imputation' is recommended to salvage rows by predicting missing or anomalous user traits based on similar profiles."
    elif is_large and len(numeric_cols) > 3:
        recommended_cleaning = "winsorize"
        cleaning_rationale = "Large-scale numerical dataset detected. 'Winsorization' is recommended to smoothly cap extreme statistical outliers without shrinking your dataset size."
    else:
        recommended_cleaning = "quarantine"
        cleaning_rationale = "Generic dataset detected. 'Quarantine' is the safest default action. It moves anomalous rows to a secure vault while keeping your main dataset perfectly clean."

    return {
        "status": "success",
        "session_id": session_id,
        "total_rows": len(df),
        "anomaly_count": sum(is_anomaly),
        "recommendation": recommendation,
        "recommended_cleaning": recommended_cleaning,
        "cleaning_rationale": cleaning_rationale,
        "parquet_path": raw_parquet_path,
    }
