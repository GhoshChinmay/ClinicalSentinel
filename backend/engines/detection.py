"""
DataSentinel — Anomaly Detection Engine
Isolation Forest anomaly detection with Velocity Engine and Threat Scoring.
"""

import uuid
import polars as pl
import pandas as pd
import numpy as np
import json
from sklearn.ensemble import IsolationForest, HistGradientBoostingClassifier
import shap

from utils import _session_dir, logger
from engines.nlp_bridge import process_text_anomalies


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
            # M-06 FIX: Log the original error before attempting pandas fallback
            logger.warning("Polars CSV read failed (%s), attempting pandas fallback...", primary_err)
            try:
                pandas_fallback = pd.read_csv(file_path, low_memory=False)
                df = pl.from_pandas(pandas_fallback)
            except Exception as inner_e:
                return {"error": f"Fatal Read Error. Both engines failed to parse the CSV: {str(inner_e)}"}

    pre_dedup = len(df)
    df = df.unique()
    logger.info("Dedup complete: %d → %d rows.", pre_dedup, len(df))

    # ---------------------------------------------------------
    # THE VELOCITY ENGINE (Time-Series Context)
    # ---------------------------------------------------------
    time_cols = [
        c for c in df.columns
        if "date" in c.lower() or "time" in c.lower() or "timestamp" in c.lower()
    ]
    entity_keywords = ["user", "account", "customer", "merchant", "employee", "sender", "client", "patient"]
    id_cols = [
        c for c in df.columns
        if "id" in c.lower() and any(kw in c.lower() for kw in entity_keywords)
    ]

    velocity_cols_added = []

    if time_cols and id_cols:
        t_col = time_cols[0]
        i_col = id_cols[0]

        logger.info("Time-Series detected. Tracking velocity for '%s' over '%s'...", i_col, t_col)

        try:
            # --- ROBUST DATETIME PARSING ---
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
                            pl.col(t_col).str.strptime(pl.Datetime, format=fmt, strict=False)
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
                    raise ValueError(f"Could not parse '{t_col}' as datetime with any known format.")

            if df[t_col].dtype == pl.Date:
                df = df.with_columns(pl.col(t_col).cast(pl.Datetime))

            df = df.filter(pl.col(t_col).is_not_null())
            df = df.sort([i_col, t_col])

            # --- SMART COLUMN SELECTION ---
            numeric_cols_for_velocity = [
                c for c, d in zip(df.columns, df.dtypes)
                if d in [pl.Float64, pl.Int64, pl.Float32, pl.Int32]
            ]
            amount_keywords = ["amount", "value", "price", "total", "balance", "sum", "cost", "payment"]
            smart_picks = [c for c in numeric_cols_for_velocity if any(kw in c.lower() for kw in amount_keywords)]
            track_col = smart_picks[0] if smart_picks else (numeric_cols_for_velocity[0] if numeric_cols_for_velocity else None)

            if track_col:
                df = df.with_columns(pl.lit(1).alias("_txn_counter"))
                df = df.with_columns([
                    pl.col(track_col).rolling_sum_by(by=t_col, window_size="1d", closed="both").over(i_col).alias("velocity_24h_sum"),
                    pl.col("_txn_counter").rolling_sum_by(by=t_col, window_size="1h", closed="both").over(i_col).alias("velocity_1h_count"),
                ])
                df = df.with_columns([
                    pl.col("velocity_24h_sum").fill_null(0),
                    pl.col("velocity_1h_count").fill_null(0),
                ])
                df = df.drop("_txn_counter")
                velocity_cols_added = ["velocity_24h_sum", "velocity_1h_count"]
                logger.info("Velocity tracking successfully generated for '%s'.", track_col)
            else:
                logger.info("Velocity Engine skipped — no numeric columns found for tracking.")
        except Exception as e:
            logger.warning("Velocity Engine skipped due to parsing error: %s", e)

    df = process_text_anomalies(df)
    pandas_df = df.to_pandas()

    numeric_cols = [c for c in pandas_df.select_dtypes(include=[np.number]).columns.tolist() if c not in time_cols]
    cat_cols = pandas_df.select_dtypes(include=["object", "string"]).columns.tolist()

    encoded_df = pandas_df[numeric_cols].copy().fillna(0)
    for col in cat_cols:
        # BUG-01 FIX: Use explicit dict so .map() works correctly across Pandas versions
        freq_encoding = pandas_df[col].value_counts(normalize=True).to_dict()
        encoded_df[col + "_freq"] = pandas_df[col].map(freq_encoding).fillna(0)

    # --- THE AI DETECTION ENGINE (Z-Score Thresholding) ---
    recommendation = "Isolation Forest (Z-Score Scaled)"

    # OPTIMIZATION: Subsample for extremely fast training on huge datasets
    max_if_samples = 50000
    if len(encoded_df) > max_if_samples:
        train_df = encoded_df.sample(n=max_if_samples, random_state=42)
    else:
        train_df = encoded_df

    model = IsolationForest(n_estimators=100, n_jobs=-1, random_state=42)
    model.fit(train_df)

    raw_scores = model.decision_function(encoded_df)
    inverted_scores = -raw_scores

    mean_weirdness = np.mean(inverted_scores)
    std_weirdness = np.std(inverted_scores)

    threshold = mean_weirdness + (1.5 * std_weirdness)
    is_anomaly = [bool(s > threshold) for s in inverted_scores]

    df = df.with_columns(pl.Series(name="is_anomaly", values=is_anomaly))

    # --- SHAP EXPLAINABILITY LAYER ---
    try:
        logger.info("Computing SHAP values for anomaly attribution...")
        explainer = shap.TreeExplainer(model)
        
        anomaly_indices = [i for i, x in enumerate(is_anomaly) if x]
        feature_names = encoded_df.columns.tolist()
        shap_payloads = ["[]"] * len(pandas_df)

        if anomaly_indices:
            # Removed optimization cap: user wants all anomalies to have full feature reasoning

            anom_encoded_df = encoded_df.iloc[anomaly_indices]
            shap_vals = explainer.shap_values(anom_encoded_df)
            
            for j, orig_idx in enumerate(anomaly_indices):
                row_shap = shap_vals[j]
                # Sort by absolute magnitude to find top 3 impactful features
                top_indices = np.argsort(np.abs(row_shap))[-3:][::-1]
                
                contributions = []
                for idx in top_indices:
                    contributions.append({
                        "feature": feature_names[idx],
                        "impact": float(row_shap[idx])
                    })
                shap_payloads[orig_idx] = json.dumps(contributions)

        df = df.with_columns(pl.Series(name="SHAP_Payload", values=shap_payloads))
        logger.info("SHAP attribution successfully embedded.")
    except Exception as e:
        logger.warning("SHAP attribution failed: %s", e)
        df = df.with_columns(pl.Series(name="SHAP_Payload", values=["[]"] * len(pandas_df)))

    # --- TIER 2 THREAT ENGINE (SUPERVISED OR SYNTHETIC) ---
    if "Class" in pandas_df.columns:
        try:
            X = encoded_df.drop(columns=["Class"]) if "Class" in encoded_df.columns else encoded_df
            y = pandas_df["Class"].fillna(0)

            max_train_samples = 50000
            if len(X) > max_train_samples:
                sample_idx = np.random.choice(len(X), size=max_train_samples, replace=False)
                X_train = X.iloc[sample_idx]
                y_train = y.iloc[sample_idx]
            else:
                X_train = X
                y_train = y

            classifier = HistGradientBoostingClassifier(class_weight="balanced", random_state=42)
            classifier.fit(X_train, y_train)

            probabilities = classifier.predict_proba(X)[:, 1]
            threat_scores = [round(p * 100, 2) for p in probabilities]
            df = df.with_columns(pl.Series(name="Threat_Score", values=threat_scores))
        except Exception as e:
            logger.warning("Supervised Engine failed: %s", e)
            df = df.with_columns(pl.Series(name="Threat_Score", values=[0] * len(pandas_df)))
    else:
        try:
            min_s = inverted_scores.min()
            max_s = inverted_scores.max()

            threat_scores = []
            if max_s > min_s:
                for i, s in enumerate(inverted_scores):
                    if is_anomaly[i]:
                        range_anom = max_s - threshold
                        score = 60 + (((s - threshold) / range_anom) * 40) if range_anom > 0 else 100
                    else:
                        range_norm = threshold - min_s
                        score = (((s - min_s) / range_norm) * 40) if range_norm > 0 else 0

                    threat_scores.append(min(100.0, max(0.0, round(score, 2))))
            else:
                threat_scores = [0] * len(pandas_df)

            df = df.with_columns(pl.Series(name="Threat_Score", values=threat_scores))
        except Exception as e:
            logger.warning("Synthetic Engine failed: %s", e)
            df = df.with_columns(pl.Series(name="Threat_Score", values=[0] * len(pandas_df)))

    logger.info("FINISHED THREAT ENGINE")

    # --- AI REASON GENERATOR ---
    engineered_suffixes = ("_length", "_digit_ratio", "_upper_ratio", "_special_ratio")
    engineered_prefixes = ("nlp_pc",)
    velocity_col_names = set(velocity_cols_added)

    original_numeric = [
        c for c in numeric_cols
        if not c.endswith(engineered_suffixes)
        and not any(c.startswith(p) for p in engineered_prefixes)
        and c not in velocity_col_names
    ]

    reasons_list = [""] * len(pandas_df)

    if any(is_anomaly):
        stats = {}
        for col in original_numeric:
            # BUG-02 FIX: Coerce NaN std (e.g. all-null or single-row columns) to 0
            stats[col] = {"mean": pandas_df[col].mean() or 0, "std": pandas_df[col].std() or 0}

        velocity_stats = {}
        for vc in velocity_cols_added:
            if vc in pandas_df.columns:
                velocity_stats[vc] = {"mean": pandas_df[vc].mean(), "std": pandas_df[vc].std()}

        rare_cats = {}
        for col in cat_cols:
            counts = pandas_df[col].value_counts(normalize=True)
            rare_cats[col] = counts[counts < 0.01].index.tolist()

        anomaly_indices = [i for i, x in enumerate(is_anomaly) if x]
        
        # Removing optimization cap: the user specifically requested every single anomaly to have reasoning.

        for idx in anomaly_indices:
            row = pandas_df.iloc[idx]
            reasons = []

            for vc in velocity_cols_added:
                if vc in pandas_df.columns and vc in velocity_stats:
                    vc_mean = velocity_stats[vc]["mean"]
                    vc_std = velocity_stats[vc]["std"]
                    if vc_std > 0 and row[vc] > vc_mean + (2.5 * vc_std):
                        if "24h" in vc:
                            reasons.append(f"Velocity spike: 24-hour rolling total ({row[vc]:.1f}) far exceeds the norm ({vc_mean:.1f}).")
                        elif "1h" in vc:
                            reasons.append(f"Burst detected: {int(row[vc])} events in 1 hour vs. average of {vc_mean:.1f}.")

            for col in original_numeric:
                col_mean = stats[col]["mean"]
                col_std = stats[col]["std"]

                if col_std > 0 and row[col] > col_mean + (2.5 * col_std):
                    reasons.append(f"'{col}' ({row[col]:.1f}) is exceptionally high compared to the average ({col_mean:.1f}).")
                elif col_std > 0 and row[col] < col_mean - (2.5 * col_std):
                    reasons.append(f"'{col}' ({row[col]:.1f}) is suspiciously low compared to normal patterns.")

            for col in cat_cols:
                val = str(row[col])
                if val in rare_cats[col]:
                    reasons.append(f"The text '{val}' in '{col}' is extremely rare (possible typo).")

            if not reasons:
                reasons.append("Complex anomaly: The combination of these variables breaks standard dataset patterns.")

            reasons_list[idx] = " | ".join(reasons[:3])

    df = df.with_columns(pl.Series(name="AI_Reason", values=reasons_list))
    logger.info("FINISHED REASON GENERATOR")
    raw_parquet_path = f"{session_dir}/raw_data.parquet"
    df.write_parquet(raw_parquet_path)

    # ---------------------------------------------------------
    # SMART CLEANING RECOMMENDATION ENGINE
    # ---------------------------------------------------------
    col_str = " ".join(df.columns).lower()

    text_heavy = len(cat_cols) >= len(numeric_cols) and len(cat_cols) > 0
    is_large = len(pandas_df) > 2000
    has_time = len(time_cols) > 0

    if text_heavy or any(kw in col_str for kw in ["review", "text", "description", "summary", "comment", "feedback"]):
        recommended_cleaning = "mask"
        cleaning_rationale = "Text-heavy dataset detected. We recommend 'Masking' to safely redact anomalous strings, typos, or bot-generated text with a [REDACTED] tag without destroying the rest of the row."
    elif any(kw in col_str for kw in ["amount", "transaction", "fraud", "price", "payment", "bank", "credit", "merchant", "card"]):
        recommended_cleaning = "quarantine"
        cleaning_rationale = "Financial or Security data detected. 'Quarantine' is strictly recommended to isolate threats and anomalies without erasing the forensic evidence."
    elif has_time and any(kw in col_str for kw in ["sensor", "temp", "reading", "humidity", "metric", "iot", "cpu", "memory", "speed"]):
        recommended_cleaning = "impute"
        cleaning_rationale = "Sequential telemetry/sensor data detected. 'Predictive KNN Imputation' is recommended to smoothly bridge over hardware glitches or dropped signals."
    elif any(kw in col_str for kw in ["age", "passenger", "survived", "income", "gender", "sex", "patient", "blood", "disease", "fare"]):
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
