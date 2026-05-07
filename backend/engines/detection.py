"""
ClinicalSentinel — Anomaly Detection Engine
Isolation Forest anomaly detection enriched with Clinical Forensic Math 
(Benford's Law, Round-Number Entropy), Velocity Engine, Threat Scoring,
and Neuro-Symbolic Logic Gating.
"""

import uuid
import os
import polars as pl
import pandas as pd
import numpy as np
import json
import random
from sklearn.ensemble import IsolationForest, HistGradientBoostingClassifier
from sklearn.neighbors import LocalOutlierFactor
import shap

try:
    from pyod.models.ecod import ECOD
    ECOD_AVAILABLE = True
except ImportError:
    ECOD_AVAILABLE = False

try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

from utils import _session_dir, logger
from engines.nlp_bridge import process_text_anomalies
from engines.logic_gate import apply_logic_gate

# NEW: Import our clinical math toolkit
from engines.clinical_math import (
    calculate_benfords_law_score,
    calculate_round_number_risk,
    calculate_last_digit_entropy
)

# Maximum number of statistical anomalies to run SHAP on.
# Prevents multi-minute hangs on large flagged sets.
_SHAP_MAX_ROWS = 500

# ---------------------------------------------------------------------------
# NARRATIVE HELPERS  (used exclusively by Stage 6)
# ---------------------------------------------------------------------------

# Known abbreviations / jargon → plain English
_FEATURE_NAME_MAP: dict[str, str] = {
    "amt": "amount",
    "txn": "transaction",
    "trx": "transaction",
    "qty": "quantity",
    "num": "number of",
    "cnt": "count",
    "freq": "frequency",
    "pct": "percentage",
    "avg": "average",
    "std": "spread",
    "diff": "difference",
    "prev": "previous",
    "curr": "current",
    "bal": "balance",
    "acct": "account",
    "cust": "customer",
    "src": "source",
    "dst": "destination",
    "loc": "location",
    "ts": "timestamp",
    "dt": "date",
    "hr": "hour",
    "min": "minute",
    "sec": "second",
    "id": "ID",
    "ip": "IP address",
    "lat": "latitude",
    "lon": "longitude",
}

# Internal suffixes that carry no meaning to an end user
_STRIP_SUFFIXES = (
    "_freq", "_entity_z", "_length", "_digit_ratio",
    "_upper_ratio", "_special_ratio", 
)


def _humanize_feature_name(col: str) -> str:
    """
    Convert an internal column name to a readable label.
    """
    # Special-case velocity / LSTM features
    if col.startswith("velocity_24h"):
        return "24-hour Activity Volume"
    if col.startswith("velocity_1h"):
        return "Hourly Transaction Count"
    if col.startswith("lstm_"):
        return "Behavioural Pattern Score"
    if col.startswith("lof_"):
        return "Local Outlier Score"
    if col.startswith("ecod_"):
        return "Distribution Outlier Score"
    if col.startswith("nlp_pc"):
        return "Text Pattern"

    # NEW: Special-case Clinical Math features
    if col.endswith("_benford_risk"):
        base = col.replace("_benford_risk", "")
        return f"Benford's Law Deviation in {_humanize_feature_name(base)}"
    if col.endswith("_round_risk"):
        base = col.replace("_round_risk", "")
        return f"Round-Number Fabrication in {_humanize_feature_name(base)}"
    if col.endswith("_entropy_risk"):
        base = col.replace("_entropy_risk", "")
        return f"Last-Digit Entropy Anomaly in {_humanize_feature_name(base)}"

    # Strip known internal suffixes
    name = col
    for suffix in _STRIP_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break

    # Replace underscores, apply abbreviation map word-by-word
    words = name.replace("-", "_").split("_")
    expanded = []
    for w in words:
        lower_w = w.lower()
        expanded.append(_FEATURE_NAME_MAP.get(lower_w, w))

    readable = " ".join(expanded).strip().title()
    return readable or col


def _describe_deviation(z: float) -> tuple[str, str]:
    direction = "high" if z > 0 else "low"
    abs_z = abs(z)

    if abs_z < 1.5:
        severity = f"slightly {direction}"
        context = "a little outside the normal range"
    elif abs_z < 2.5:
        severity = f"notably {direction}"
        context = "noticeably different from the typical value"
    elif abs_z < 3.5:
        severity = f"significantly {direction}"
        context = "well outside what is normally seen"
    elif abs_z < 5.0:
        severity = f"exceptionally {direction}"
        context = "far beyond the expected range"
    else:
        severity = f"extremely {direction}"
        context = "at an extreme level rarely seen in this dataset"

    return severity, context


def _format_value(val, col: str) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "unknown"

    col_lower = col.lower()

    if any(kw in col_lower for kw in ("amount", "price", "balance", "total", "cost", "payment", "fare", "revenue", "salary", "income")):
        try:
            return f"${float(val):,.2f}"
        except (ValueError, TypeError):
            pass

    if any(kw in col_lower for kw in ("prob", "pct", "percent", "ratio", "rate", "score")):
        try:
            f_val = float(val)
            if 0 <= f_val <= 1:
                return f"{f_val * 100:.1f}%"
        except (ValueError, TypeError):
            pass

    if any(kw in col_lower for kw in ("age", "days", "hours", "minutes", "years")):
        try:
            return str(int(round(float(val))))
        except (ValueError, TypeError):
            pass

    if isinstance(val, float):
        return f"{val:,.2f}" if abs(val) >= 1 else f"{val:.4f}"

    return str(val)


def _detect_domain(col_str: str) -> str:
    _finance = ["amount", "transaction", "fraud", "payment", "bank", "credit", "merchant", "card", "debit", "wire"]
    _health = ["patient", "blood", "disease", "diagnosis", "medication", "dose", "bmi", "cholesterol"]
    _hr = ["employee", "salary", "department", "hire", "termination", "leave", "payroll"]
    _iot = ["sensor", "temp", "humidity", "cpu", "memory", "voltage", "current", "reading", "device"]
    _ecomm = ["order", "cart", "product", "sku", "shipment", "return", "review", "rating"]

    if any(kw in col_str for kw in _finance):
        return "finance"
    if any(kw in col_str for kw in _health):
        return "health"
    if any(kw in col_str for kw in _hr):
        return "hr"
    if any(kw in col_str for kw in _iot):
        return "iot"
    if any(kw in col_str for kw in _ecomm):
        return "ecommerce"
    return "generic"


_DOMAIN_SUBJECT: dict[str, str] = {
    "finance": "This transaction",
    "health": "This record",
    "hr": "This employee record",
    "iot": "This reading",
    "ecommerce": "This order",
    "generic": "This record",
}

_DOMAIN_ENTITY: dict[str, str] = {
    "finance": "account",
    "health": "patient",
    "hr": "employee",
    "iot": "device",
    "ecommerce": "customer",
    "generic": "entity",
}


def _build_logic_violation_narrative(raw_violation: str) -> str:
    if not raw_violation or not isinstance(raw_violation, str):
        return "A data integrity rule was broken — the values in this record are logically inconsistent."

    raw = raw_violation.strip()

    if "violated:" in raw.lower():
        parts = raw.lower().split("violated:", 1)
        rule_part = parts[0].strip().rstrip(".")
        detail_part = parts[1].strip() if len(parts) > 1 else ""

        rule_readable = rule_part.replace("_", " ").replace("  ", " ")
        if detail_part:
            field_val = detail_part.replace("_", " ").replace("=", " of ").replace(",", " and")
            return (
                f"A data integrity check failed — the rule '{rule_readable}' was not met "
                f"(recorded value: {field_val}). This suggests the data may be corrupted, "
                f"entered incorrectly, or physically impossible."
            )
        return (
            f"A business logic rule was violated: '{rule_readable}'. "
            f"This kind of inconsistency usually points to a data entry error or system fault."
        )

    clean = raw.replace("_", " ").replace("  ", " ").rstrip(".")
    return (
        f"This record failed an internal consistency check: {clean}. "
        f"It may reflect a data entry error, system fault, or deliberate manipulation."
    )


def process_and_detect(
    file_path: str = None,
    session_id: str = None,
    algorithm: str = "isolation_forest",
    df: pl.DataFrame = None,
):
    if not session_id:
        session_id = str(uuid.uuid4())

    session_dir = _session_dir(session_id)

    _supported_algorithms = {"isolation_forest", "lof", "ecod"}
    algorithm = algorithm.lower().strip()
    if algorithm not in _supported_algorithms:
        logger.warning(
            "Unknown algorithm '%s'. Falling back to 'isolation_forest'.", algorithm
        )
        algorithm = "isolation_forest"

    if df is None:
        try:
            df = pl.read_csv(file_path, infer_schema_length=1_000_000)
        except Exception as primary_err:
            logger.warning("Polars CSV read failed (%s), attempting pandas fallback...", primary_err)
            try:
                pandas_fallback = pd.read_csv(file_path, low_memory=False)
                df = pl.from_pandas(pandas_fallback)
            except Exception as inner_e:
                return {
                    "error": f"Fatal Read Error. Both engines failed to parse the CSV: {inner_e}"
                }

    pre_dedup = len(df)
    df = df.unique()
    logger.info("Dedup complete: %d → %d rows.", pre_dedup, len(df))

    # STAGE 1: THE NEURO-SYMBOLIC LOGIC GATE
    df, applied_rules = apply_logic_gate(df)

    # STAGE 2: THE VELOCITY ENGINE
    time_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower() or "timestamp" in c.lower()]
    entity_keywords = ["user", "account", "customer", "merchant", "employee", "sender", "client", "patient", "investigator", "site"]
    id_cols = [c for c in df.columns if "id" in c.lower() and any(kw in c.lower() for kw in entity_keywords)]
    
    # Fallback: if no specific keyword matched, grab ANY 'id' column just for grouping purposes
    if not id_cols:
        id_cols = [c for c in df.columns if "id" in c.lower()]

    velocity_cols_added: list[str] = []
    lstm_score_available = False

    if time_cols and id_cols:
        t_col = time_cols[0]
        i_col = id_cols[0]

        logger.info("Time-Series detected. Tracking velocity for '%s' over '%s'...", i_col, t_col)

        try:
            if df[t_col].dtype not in [pl.Datetime, pl.Date]:
                parsed = None
                datetime_formats = [
                    "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d",
                    "%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S",
                ]
                for fmt in datetime_formats:
                    try:
                        candidate = df.with_columns(
                            pl.col(t_col).str.strptime(pl.Datetime, format=fmt, strict=False)
                        )
                        if candidate[t_col].null_count() / len(candidate) < 0.5:
                            df = candidate
                            parsed = candidate
                            logger.info("Parsed '%s' with format '%s'.", t_col, fmt)
                            break
                    except Exception:
                        continue

                if parsed is None:
                    raise ValueError(f"Could not parse '{t_col}' as datetime.")

            if df[t_col].dtype == pl.Date:
                df = df.with_columns(pl.col(t_col).cast(pl.Datetime))

            df = df.filter(pl.col(t_col).is_not_null())
            df = df.sort([i_col, t_col])

            numeric_cols_for_velocity = [
                c for c, d in zip(df.columns, df.dtypes)
                if d in [pl.Float64, pl.Int64, pl.Float32, pl.Int32]
            ]
            amount_keywords = ["amount", "value", "price", "total", "balance", "sum", "cost", "payment", "blood", "rate"]
            smart_picks = [c for c in numeric_cols_for_velocity if any(kw in c.lower() for kw in amount_keywords)]
            track_col = smart_picks[0] if smart_picks else (numeric_cols_for_velocity[0] if numeric_cols_for_velocity else None)

            if track_col:
                df = df.with_columns(pl.lit(1).alias("_txn_counter"))
                df = df.with_columns(
                    [
                        pl.col(track_col).rolling_sum_by(by=t_col, window_size="1d", closed="both").over(i_col).alias("velocity_24h_sum"),
                        pl.col("_txn_counter").rolling_sum_by(by=t_col, window_size="1h", closed="both").over(i_col).alias("velocity_1h_count"),
                    ]
                )
                df = df.with_columns([pl.col("velocity_24h_sum").fill_null(0), pl.col("velocity_1h_count").fill_null(0)])
                df = df.drop("_txn_counter")
                velocity_cols_added = ["velocity_24h_sum", "velocity_1h_count"]
                
                try:
                    import tensorflow as tf  
                    from tensorflow import keras  
                    seq_df = df.select([i_col, t_col, track_col]).to_pandas()
                    seq_df = seq_df.sort_values([i_col, t_col])

                    SEQ_LEN = 10
                    sequences: list[np.ndarray] = []
                    seq_index_map: list[int] = []

                    for _, grp in seq_df.groupby(i_col, sort=False):
                        vals = grp[track_col].fillna(0).values.astype("float32")
                        v_std = vals.std() if vals.std() > 0 else 1.0
                        vals = (vals - vals.mean()) / v_std
                        idxs = grp.index.tolist()
                        for j in range(len(vals) - SEQ_LEN + 1):
                            sequences.append(vals[j: j + SEQ_LEN])
                            seq_index_map.append(idxs[j + SEQ_LEN - 1])

                    if len(sequences) >= 20:
                        X_seq = np.array(sequences, dtype="float32").reshape(-1, SEQ_LEN, 1)
                        inp = keras.Input(shape=(SEQ_LEN, 1))
                        enc = keras.layers.LSTM(16, activation="relu")(inp)
                        rep = keras.layers.RepeatVector(SEQ_LEN)(enc)
                        dec = keras.layers.LSTM(16, activation="relu", return_sequences=True)(rep)
                        out = keras.layers.TimeDistributed(keras.layers.Dense(1))(dec)
                        autoencoder = keras.Model(inp, out)
                        autoencoder.compile(optimizer="adam", loss="mse")
                        autoencoder.fit(X_seq, X_seq, epochs=5, batch_size=64, verbose=0)

                        recon = autoencoder.predict(X_seq, verbose=0)
                        recon_errors = np.mean(np.abs(X_seq - recon), axis=(1, 2))

                        lstm_scores_arr = np.zeros(len(df))
                        seq_df_index_list = seq_df.index.tolist()
                        for k, orig_idx in enumerate(seq_index_map):
                            try:
                                pos_in_df = seq_df_index_list.index(orig_idx)
                                lstm_scores_arr[pos_in_df] = max(lstm_scores_arr[pos_in_df], recon_errors[k])
                            except ValueError:
                                pass

                        df = df.with_columns(pl.Series(name="lstm_anomaly_score", values=lstm_scores_arr.tolist()))
                        lstm_score_available = True
                except Exception as e:
                    pass
        except Exception as e:
            pass

    # FEATURE ENGINEERING
    df = process_text_anomalies(df)
    pandas_df = df.to_pandas()

    numeric_cols = [c for c in pandas_df.select_dtypes(include=[np.number]).columns.tolist() if c not in time_cols]
    cat_cols = pandas_df.select_dtypes(include=["object", "string"]).columns.tolist()

    if "logic_violation" in cat_cols:
        cat_cols.remove("logic_violation")

    encoded_df = pandas_df[numeric_cols].copy().fillna(0)
    for col in cat_cols:
        freq_encoding = pandas_df[col].value_counts(normalize=True).to_dict()
        encoded_df[col + "_freq"] = pandas_df[col].map(freq_encoding).fillna(0)

    if lstm_score_available and "lstm_anomaly_score" in pandas_df.columns:
        encoded_df["lstm_anomaly_score"] = pandas_df["lstm_anomaly_score"].fillna(0).values

    # -----------------------------------------------------------------
    # CLINICAL SENTINEL FORENSIC MATH (Layers 1, 4, 5)
    # Detects human fabrication via Benford's Law and Number Entropy
    # -----------------------------------------------------------------
    logger.info("Injecting Clinical Sentinel Forensic Math features...")
    clinical_cols_added = []
    
    # If no specific ID exists, we treat the dataset as one global entity
    group_col = id_cols[0] if id_cols else None
    
    # Filter numeric cols to only continuous measurements (ignore IDs, booleans)
    clinical_targets = [c for c in numeric_cols if c != group_col and pandas_df[c].nunique() > 10]
    
    for col in clinical_targets[:3]: # Cap at top 3 numerical columns to prevent feature explosion
        if group_col:
            # Group by Investigator/Site/Entity
            grouped = pandas_df.groupby(group_col)[col]
            
            # Layer 1: Benford's Law
            benford_map = grouped.apply(lambda x: calculate_benfords_law_score(x)["risk_score"]).to_dict()
            encoded_df[f"{col}_benford_risk"] = pandas_df[group_col].map(benford_map).fillna(0)
            
            # Layer 4: Round Number Fabrication
            round_map = grouped.apply(lambda x: calculate_round_number_risk(x)["risk_score"]).to_dict()
            encoded_df[f"{col}_round_risk"] = pandas_df[group_col].map(round_map).fillna(0)
            
            # Layer 5: Last Digit Entropy
            entropy_map = grouped.apply(lambda x: calculate_last_digit_entropy(x)["risk_score"]).to_dict()
            encoded_df[f"{col}_entropy_risk"] = pandas_df[group_col].map(entropy_map).fillna(0)
        else:
            # Global fallback (If testing on non-clinical datasets without IDs)
            encoded_df[f"{col}_benford_risk"] = calculate_benfords_law_score(pandas_df[col])["risk_score"]
            encoded_df[f"{col}_round_risk"] = calculate_round_number_risk(pandas_df[col])["risk_score"]
            encoded_df[f"{col}_entropy_risk"] = calculate_last_digit_entropy(pandas_df[col])["risk_score"]
            
        clinical_cols_added.extend([f"{col}_benford_risk", f"{col}_round_risk", f"{col}_entropy_risk"])
    
    if clinical_cols_added:
        logger.info(f"Clinical features successfully added: {clinical_cols_added}")

    # ENTITY-RELATIVE Z-SCORE FEATURES
    entity_zscore_cols_added: list[str] = []
    if id_cols:
        i_col_enc = id_cols[0]
        if i_col_enc in pandas_df.columns:
            amount_kws = ["amount", "value", "price", "total", "balance", "sum", "cost", "payment"]
            entity_target_cols = [c for c in numeric_cols if any(kw in c.lower() for kw in amount_kws) and c not in ("velocity_24h_sum", "velocity_1h_count")][:3]

            if entity_target_cols:
                entity_groups = pandas_df.groupby(i_col_enc)
                for col in entity_target_cols:
                    entity_mean = entity_groups[col].transform("mean")
                    entity_std = entity_groups[col].transform("std").fillna(1).replace(0, 1)
                    z_col = f"{col}_entity_z"
                    encoded_df[z_col] = ((pandas_df[col] - entity_mean) / entity_std).fillna(0)
                    entity_zscore_cols_added.append(z_col)

    # STAGE 2.5: ECOD
    ecod_score_added = False
    if ECOD_AVAILABLE and len(encoded_df) > 0:
        try:
            ecod_safe_df = encoded_df.loc[:, encoded_df.nunique() > 1]
            if not ecod_safe_df.empty and len(ecod_safe_df.columns) > 0:
                ecod = ECOD()
                ecod.fit(ecod_safe_df.values)
                encoded_df = encoded_df.copy()
                encoded_df["ecod_score"] = ecod.decision_scores_
                ecod_score_added = True
        except Exception:
            pass

    # STAGE 3: THE AI DETECTION ENGINE
    _algo_label_parts = []
    if ecod_score_added:
        _algo_label_parts.append("ECOD-enriched")

    if algorithm == "ecod" and ecod_score_added:
        recommendation = "ECOD-only (Empirical CDF)"
        inverted_scores = encoded_df["ecod_score"].values if "ecod_score" in encoded_df else np.zeros(len(encoded_df))
        model = None
        model_fitted = bool(ecod_score_added)
    elif algorithm == "lof":
        recommendation = "LOF-only (Local Outlier Factor)"
        model = None
        model_fitted = False
        inverted_scores = np.zeros(len(encoded_df))
    else:
        _algo_label_parts.append("Isolation Forest + LOF Ensemble")
        recommendation = " + ".join(_algo_label_parts) + " (Z-Score Scaled)"

    clean_encoded_df = encoded_df
    if "logic_violation" in pandas_df.columns:
        clean_encoded_df = encoded_df[pandas_df["logic_violation"].isna()]

    max_if_samples = 50_000
    if len(clean_encoded_df) > max_if_samples:
        train_df = clean_encoded_df.sample(n=max_if_samples, random_state=42)
    else:
        train_df = clean_encoded_df

    model_fitted = False
    model = None

    if len(train_df) == 0:
        train_df = encoded_df

    col_str_check = " ".join(pandas_df.columns).lower()
    _finance_kws = ["amount", "transaction", "fraud", "payment", "bank", "credit", "merchant", "card"]
    _demo_kws = ["age", "passenger", "income", "gender", "patient", "blood", "disease", "fare"]
    if any(kw in col_str_check for kw in _finance_kws):
        _sigma_mult = 1.2
    elif any(kw in col_str_check for kw in _demo_kws):
        _sigma_mult = 2.0
    else:
        _sigma_mult = 1.5

    if algorithm != "lof" and len(train_df) > 0:
        model = IsolationForest(n_estimators=100, n_jobs=-1, random_state=42)
        model.fit(train_df)
        raw_scores = model.decision_function(encoded_df)
        inverted_scores = -raw_scores
        mean_weirdness = np.mean(inverted_scores)
        std_weirdness = np.std(inverted_scores)
        threshold = mean_weirdness + (_sigma_mult * std_weirdness)
        model_fitted = True
    elif algorithm == "lof":
        threshold = 1.0
    elif algorithm == "ecod" and ecod_score_added:
        mean_w = np.mean(inverted_scores)
        std_w = np.std(inverted_scores)
        threshold = mean_w + (_sigma_mult * std_w)
        model_fitted = True
    else:
        inverted_scores = np.zeros(len(encoded_df))
        threshold = 1.0

    is_anomaly: list[bool] = []
    if len(inverted_scores) > 0:
        for i, s in enumerate(inverted_scores):
            has_logic_error = "logic_violation" in pandas_df.columns and pd.notna(pandas_df.at[i, "logic_violation"])
            is_anomaly.append(bool((model_fitted and s > threshold) or has_logic_error))

    # STAGE 3.5: LOCAL OUTLIER FACTOR (LOF)
    lof_scores = np.zeros(len(encoded_df))
    if len(clean_encoded_df) > 0 and algorithm in ("isolation_forest", "ecod", "lof"):
        try:
            lof = LocalOutlierFactor(n_neighbors=20, novelty=True, n_jobs=-1)
            lof.fit(clean_encoded_df)
            lof_raw = lof.score_samples(encoded_df)
            lof_scores = -lof_raw

            lof_mean = np.mean(lof_scores)
            lof_std = np.std(lof_scores)
            lof_threshold = lof_mean + (_sigma_mult * lof_std)

            if algorithm == "lof":
                model_fitted = True
                inverted_scores = lof_scores
                threshold = lof_threshold
                is_anomaly = []
                for i, s in enumerate(lof_scores):
                    has_logic_error = "logic_violation" in pandas_df.columns and pd.notna(pandas_df.at[i, "logic_violation"])
                    is_anomaly.append(bool(s > lof_threshold or has_logic_error))
            else:
                for i in range(len(is_anomaly)):
                    has_logic_error = "logic_violation" in pandas_df.columns and pd.notna(pandas_df.at[i, "logic_violation"])
                    if not is_anomaly[i] and not has_logic_error:
                        if lof_scores[i] > lof_threshold:
                            is_anomaly[i] = True
        except Exception:
            pass

    df = df.with_columns(pl.Series(name="lof_score", values=lof_scores.tolist()))

    # THE ANOMALY OVERLOAD SHIELD
    logic_flags = sum(1 for i in range(len(pandas_df)) if "logic_violation" in pandas_df.columns and pd.notna(pandas_df.at[i, "logic_violation"]))
    if len(pandas_df) > 0 and (logic_flags / len(pandas_df)) > 0.90:
        if "logic_violation" in pandas_df.columns:
            pandas_df["logic_violation"] = np.nan
        is_anomaly = [bool(model_fitted and s > threshold) for s in inverted_scores]

    _cap_kws_finance = ["amount", "transaction", "fraud", "payment", "bank", "credit", "merchant", "card"]
    _cap_kws_demo = ["age", "passenger", "income", "gender", "patient", "blood", "disease", "fare"]
    _col_check = " ".join(pandas_df.columns).lower()
    if any(kw in _col_check for kw in _cap_kws_finance):
        _anomaly_cap = 0.10
    elif any(kw in _col_check for kw in _cap_kws_demo):
        _anomaly_cap = 0.20
    else:
        _anomaly_cap = 0.15

    stat_anomaly_count = sum(1 for i, x in enumerate(is_anomaly) if x and not ("logic_violation" in pandas_df.columns and pd.notna(pandas_df.at[i, "logic_violation"])))
    if len(pandas_df) > 0 and stat_anomaly_count / len(pandas_df) > _anomaly_cap:
        if len(inverted_scores) > 0:
            top_threshold = np.percentile(inverted_scores, (1 - _anomaly_cap) * 100)
            for i, x in enumerate(is_anomaly):
                if x and not ("logic_violation" in pandas_df.columns and pd.notna(pandas_df.at[i, "logic_violation"])):
                    if inverted_scores[i] < top_threshold:
                        is_anomaly[i] = False

    if len(is_anomaly) < len(df):
        is_anomaly.extend([False] * (len(df) - len(is_anomaly)))

    df = df.with_columns(pl.Series(name="is_anomaly", values=is_anomaly))

    # STAGE 4: SHAP EXPLAINABILITY LAYER
    shap_payloads = ["[]"] * len(pandas_df)
    try:
        if model_fitted and model is not None:
            explainer = shap.TreeExplainer(model)
            stat_anomaly_indices = [i for i, x in enumerate(is_anomaly) if x and not ("logic_violation" in pandas_df.columns and pd.notna(pandas_df.at[i, "logic_violation"]))]

            if len(stat_anomaly_indices) > _SHAP_MAX_ROWS:
                stat_anomaly_indices = stat_anomaly_indices[:_SHAP_MAX_ROWS]

            feature_names = encoded_df.columns.tolist()

            if stat_anomaly_indices:
                anom_encoded_df = encoded_df.iloc[stat_anomaly_indices]
                shap_vals = explainer.shap_values(anom_encoded_df)

                for j, orig_idx in enumerate(stat_anomaly_indices):
                    row_shap = shap_vals[j]
                    top_indices = np.argsort(np.abs(row_shap))[-3:][::-1]
                    contributions = [{"feature": feature_names[idx], "impact": float(row_shap[idx])} for idx in top_indices]
                    shap_payloads[orig_idx] = json.dumps(contributions)

        df = df.with_columns(pl.Series(name="SHAP_Payload", values=shap_payloads))
    except Exception:
        df = df.with_columns(pl.Series(name="SHAP_Payload", values=["[]"] * len(pandas_df)))

    # STAGE 4.5: COUNTERFACTUAL EXPLANATIONS (DiCE)
    counterfactual_payloads = ["{}"] * len(pandas_df)
    try:
        import dice_ml  
        if model_fitted and model is not None and any(is_anomaly):
            pseudo_labels = [int(x) for x in is_anomaly]
            cf_df = encoded_df.copy().astype(float)
            cf_df["_target"] = pseudo_labels

            dice_data = dice_ml.Data(dataframe=cf_df, continuous_features=cf_df.drop(columns=["_target"]).columns.tolist(), outcome_name="_target")

            class _IFWrapper:
                def __init__(self, m: IsolationForest, thresh: float) -> None:
                    self.m = m
                    self.thresh = thresh
                def predict(self, X) -> np.ndarray:
                    arr = X.values if hasattr(X, "values") else np.asarray(X)
                    s = -self.m.decision_function(arr)
                    return (s > self.thresh).astype(int)

            wrapped = _IFWrapper(model, threshold)
            dice_model = dice_ml.Model(model=wrapped, backend="sklearn")
            exp = dice_ml.Dice(dice_data, dice_model, method="random")

            stat_anom_idxs = [i for i, x in enumerate(is_anomaly) if x and not ("logic_violation" in pandas_df.columns and pd.notna(pandas_df.at[i, "logic_violation"]))][:20]

            for orig_idx in stat_anom_idxs:
                try:
                    query = encoded_df.iloc[[orig_idx]].astype(float)
                    cf_result = exp.generate_counterfactuals(query, total_CFs=1, desired_class="opposite", verbose=False)
                    cf_dict = cf_result.cf_examples_list[0].final_cfs_df.iloc[0].to_dict()
                    original_row = encoded_df.iloc[orig_idx].to_dict()
                    changes = {
                        k: {"from": round(float(original_row[k]), 4), "to": round(float(v), 4)}
                        for k, v in cf_dict.items() if k != "_target" and abs(float(v) - float(original_row.get(k, 0))) > 1e-4
                    }
                    counterfactual_payloads[orig_idx] = json.dumps(changes)
                except Exception:
                    pass
        df = df.with_columns(pl.Series(name="Counterfactual_Payload", values=counterfactual_payloads))
    except Exception:
        df = df.with_columns(pl.Series(name="Counterfactual_Payload", values=counterfactual_payloads))

    # STAGE 5: TIER 2 THREAT ENGINE (Scoring)
    if "Class" in pandas_df.columns:
        try:
            X = encoded_df.drop(columns=["Class"]) if "Class" in encoded_df.columns else encoded_df
            y = pandas_df["Class"].fillna(0)

            max_train_samples = 50_000
            if len(X) > max_train_samples:
                sample_idx = np.random.choice(len(X), size=max_train_samples, replace=False)
                X_train, y_train = X.iloc[sample_idx], y.iloc[sample_idx]
            else:
                X_train, y_train = X, y

            neg = int((y_train == 0).sum())
            pos = int((y_train == 1).sum())
            scale_pos = neg / pos if pos > 0 else 1.0

            if XGBOOST_AVAILABLE:
                classifier = XGBClassifier(scale_pos_weight=scale_pos, eval_metric="aucpr", random_state=42, verbosity=0, use_label_encoder=False)
            else:
                classifier = HistGradientBoostingClassifier(class_weight="balanced", random_state=42)

            classifier.fit(X_train, y_train)
            probabilities = classifier.predict_proba(X)[:, 1]
            threat_scores = []
            for i, p in enumerate(probabilities):
                has_logic_error = "logic_violation" in pandas_df.columns and pd.notna(pandas_df.at[i, "logic_violation"])
                threat_scores.append(100.0 if has_logic_error else round(p * 100, 2))

            df = df.with_columns(pl.Series(name="Threat_Score", values=threat_scores))
        except Exception:
            df = df.with_columns(pl.Series(name="Threat_Score", values=[0] * len(pandas_df)))
    else:
        try:
            min_s = inverted_scores.min() if len(inverted_scores) > 0 else 0
            max_s = inverted_scores.max() if len(inverted_scores) > 0 else 0

            threat_scores = []
            if max_s > min_s:
                for i, s in enumerate(inverted_scores):
                    has_logic_error = "logic_violation" in pandas_df.columns and pd.notna(pandas_df.at[i, "logic_violation"])
                    if has_logic_error:
                        threat_scores.append(100.0)
                    elif is_anomaly[i]:
                        range_anom = max_s - threshold
                        score = 60 + (((s - threshold) / range_anom) * 40) if range_anom > 0 else 100
                        threat_scores.append(min(100.0, max(0.0, round(score, 2))))
                    else:
                        range_norm = threshold - min_s
                        score = (((s - min_s) / range_norm) * 40) if range_norm > 0 else 0
                        threat_scores.append(min(100.0, max(0.0, round(score, 2))))
            else:
                for i in range(len(pandas_df)):
                    has_logic_error = "logic_violation" in pandas_df.columns and pd.notna(pandas_df.at[i, "logic_violation"])
                    threat_scores.append(100.0 if has_logic_error else 0.0)

            df = df.with_columns(pl.Series(name="Threat_Score", values=threat_scores))
        except Exception:
            df = df.with_columns(pl.Series(name="Threat_Score", values=[0] * len(pandas_df)))

    # STAGE 6: NARRATIVE SYNTHESIS
    engineered_suffixes = ("_length", "_digit_ratio", "_upper_ratio", "_special_ratio", "_benford_risk", "_round_risk", "_entropy_risk")
    engineered_prefixes = ("nlp_pc",)
    velocity_col_names = set(velocity_cols_added)
    entity_z_col_names = set(entity_zscore_cols_added)
    clinical_col_names = set(clinical_cols_added)

    original_numeric = [
        c for c in numeric_cols
        if not c.endswith(engineered_suffixes)
        and not any(c.startswith(p) for p in engineered_prefixes)
        and c not in velocity_col_names
        and c not in entity_z_col_names
        and c not in clinical_col_names
        and c != "lstm_anomaly_score"
    ]

    _all_cols_str = " ".join(pandas_df.columns).lower()
    domain = _detect_domain(_all_cols_str)
    subject = _DOMAIN_SUBJECT[domain]       
    entity  = _DOMAIN_ENTITY[domain]        

    reasons_list = [""] * len(pandas_df)

    if any(is_anomaly):
        stats: dict[str, dict] = {}
        for col in original_numeric:
            col_mean = pandas_df[col].mean()
            col_std  = pandas_df[col].std()
            stats[col] = {
                "mean": col_mean if pd.notna(col_mean) else 0.0,
                "std":  col_std  if pd.notna(col_std)  else 0.0,
            }

        rare_cats: dict[str, list] = {}
        for col in cat_cols:
            if len(pandas_df) > 0 and pandas_df[col].nunique() / len(pandas_df) < 0.3:
                counts = pandas_df[col].value_counts(normalize=True)
                rare_cats[col] = counts[counts < 0.05].index.tolist()

        anomaly_indices = [i for i, x in enumerate(is_anomaly) if x]
        parsed_shap: dict[int, list] = {}
        if "SHAP_Payload" in df.columns:
            shap_col = df["SHAP_Payload"].to_list()
            for idx in anomaly_indices:
                try:
                    payload = json.loads(shap_col[idx])
                    if payload:
                        parsed_shap[idx] = payload
                except Exception:
                    pass

        entity_col_in_data = id_cols[0] if id_cols else None

        for idx in anomaly_indices:
            row = pandas_df.iloc[idx]
            parts: list[str] = []

            if "logic_violation" in pandas_df.columns and pd.notna(row.get("logic_violation")):
                reasons_list[idx] = _build_logic_violation_narrative(row["logic_violation"])
                continue

            if idx in parsed_shap and parsed_shap[idx]:
                shap_items = parsed_shap[idx]
                top_feat   = shap_items[0]["feature"]
                top_impact = shap_items[0]["impact"]

                orig_feat = top_feat
                for suf in _STRIP_SUFFIXES + ("_benford_risk", "_round_risk", "_entropy_risk"):
                    if orig_feat.endswith(suf):
                        orig_feat = orig_feat[: -len(suf)]
                        break

                readable_feat = _humanize_feature_name(top_feat) # Pass top_feat to catch the clinical prefix
                raw_val = row.get(orig_feat, row.get(top_feat))
                formatted_val = _format_value(raw_val, orig_feat)

                # Special case: Clinical Math Anomaly
                if top_feat in clinical_col_names:
                    if "Benford" in readable_feat:
                        parts.append(
                            f"The data distribution in the {orig_feat} field violates Benford's Law (a mathematical rule "
                            f"governing naturally occurring numbers). This specific structural anomaly is highly indicative "
                            f"of manually fabricated or manipulated data."
                        )
                    elif "Round-Number" in readable_feat:
                        parts.append(
                            f"The {orig_feat} field contains an abnormal cluster of values ending in 0 or 5. "
                            f"This lack of natural variance strongly suggests the data was rounded or entered manually."
                        )
                    elif "Entropy" in readable_feat:
                        parts.append(
                            f"The terminal digits in the {orig_feat} field lack statistical randomness. "
                            f"Fabricators often subconsciously avoid specific numbers (like 7 or 9), creating this exact pattern."
                        )

                elif top_feat in velocity_col_names or orig_feat in velocity_col_names:
                    vel_24h = row.get("velocity_24h_sum")
                    vel_1h  = row.get("velocity_1h_count")
                    if vel_1h is not None and pd.notna(vel_1h) and float(vel_1h) > 1:
                        parts.append(f"{subject} is part of a burst of {int(vel_1h)} rapid transactions from the same {entity} within a single hour — a pace that stands out as highly unusual.")
                    elif vel_24h is not None and pd.notna(vel_24h):
                        parts.append(f"The total activity from this {entity} over the past 24 hours ({_format_value(vel_24h, 'amount')}) is unusually high and well above what is normally seen in a single day.")
                    else:
                        parts.append(f"{subject} shows an abnormal spike in activity over a short window of time, which is a common indicator of automated or suspicious behaviour.")

                elif top_feat.startswith("lstm_") or orig_feat.startswith("lstm_"):
                    parts.append(f"The recent sequence of activity from this {entity} breaks away from its own established pattern. The AI detected that the order and rhythm of recent events no longer match how this {entity} normally behaves.")

                elif top_feat in entity_z_col_names or orig_feat in entity_z_col_names:
                    base_col = orig_feat.replace("_entity_z", "")
                    entity_mean_val = None
                    if entity_col_in_data and entity_col_in_data in pandas_df.columns:
                        mask = pandas_df[entity_col_in_data] == row.get(entity_col_in_data)
                        if mask.sum() > 1 and base_col in pandas_df.columns:
                            entity_mean_val = pandas_df.loc[mask, base_col].mean()
                    base_readable = _humanize_feature_name(base_col)
                    base_val = _format_value(row.get(base_col), base_col)

                    if entity_mean_val is not None and pd.notna(entity_mean_val):
                        avg_readable = _format_value(entity_mean_val, base_col)
                        parts.append(f"The {base_readable.lower()} for this entry ({base_val}) is far outside what this specific {entity} normally does — their own historical average is around {avg_readable}. This gap from their own baseline is what raised the alert.")
                    else:
                        parts.append(f"The {base_readable.lower()} here ({base_val}) is much higher than this {entity} typically records.")

                elif orig_feat in stats and stats[orig_feat]["std"] > 0:
                    raw_feat_val = row.get(orig_feat)
                    if raw_feat_val is not None and (hasattr(raw_feat_val, '__float__') or isinstance(raw_feat_val, (int, float))):
                        z = (float(raw_feat_val) - stats[orig_feat]["mean"]) / stats[orig_feat]["std"]
                        severity, context_phrase = _describe_deviation(z)
                        avg_readable = _format_value(stats[orig_feat]["mean"], orig_feat)
                        openers = [
                            f"The {readable_feat.lower()} for this record is {formatted_val}, which is {severity} — {context_phrase}. The typical value across the dataset is around {avg_readable}.",
                            f"What stands out most is the {readable_feat.lower()}: {formatted_val}. Compared to the usual figure of {avg_readable}, this is {severity} and {context_phrase}.",
                        ]
                        parts.append(random.choice(openers))

                elif orig_feat in rare_cats and str(raw_val) in rare_cats.get(orig_feat, []):
                    parts.append(f"The value '{raw_val}' in the {readable_feat.lower()} field is extremely uncommon — it appears in fewer than 5% of all records. Rare categories like this can indicate unusual circumstances.")
                else:
                    parts.append(f"{subject} stood out because of an unusual combination involving {readable_feat.lower()} ({formatted_val}), which the model identified as behaving differently from the rest of the data.")

                if len(shap_items) > 1 and abs(shap_items[1]["impact"]) > abs(top_impact) * 0.25:
                    sec_feat = shap_items[1]["feature"]
                    sec_orig = sec_feat
                    for suf in _STRIP_SUFFIXES + ("_benford_risk", "_round_risk", "_entropy_risk"):
                        if sec_orig.endswith(suf):
                            sec_orig = sec_orig[: -len(suf)]
                            break
                    sec_readable  = _humanize_feature_name(sec_feat)
                    sec_raw_val   = row.get(sec_orig, row.get(sec_feat))
                    sec_formatted = _format_value(sec_raw_val, sec_orig)
                    
                    if sec_feat in clinical_col_names:
                        parts.append(f"This is compounded by another structural anomaly detected in the {sec_orig} field, indicating high statistical manipulation risk.")
                    elif sec_orig in stats and stats[sec_orig]["std"] > 0:
                        z2 = (row[sec_orig] - stats[sec_orig]["mean"]) / stats[sec_orig]["std"]
                        sev2, ctx2 = _describe_deviation(z2)
                        parts.append(f"On top of that, the {sec_readable.lower()} ({sec_formatted}) is also {sev2}, adding to the concern.")
                    elif sec_orig in rare_cats and str(sec_raw_val) in rare_cats.get(sec_orig, []):
                        parts.append(f"Adding to this, '{sec_raw_val}' is a very rare value for {sec_readable.lower()}, which reinforces the flag.")
                    else:
                        parts.append(f"A secondary signal came from the {sec_readable.lower()} field ({sec_formatted}), which also looked out of place.")

                reasons_list[idx] = " ".join(parts)
            else:
                max_z, max_col, sec_z, sec_col = 0.0, None, 0.0, None
                for col in original_numeric:
                    if stats.get(col, {}).get("std", 0) > 0:
                        z = abs((row[col] - stats[col]["mean"]) / stats[col]["std"])
                        if z > max_z:
                            sec_z, sec_col = max_z, max_col
                            max_z, max_col = z, col
                        elif z > sec_z:
                            sec_z, sec_col = z, col

                if max_col and max_z > 2.0:
                    readable_max  = _humanize_feature_name(max_col)
                    formatted_max = _format_value(row[max_col], max_col)
                    sev, ctx      = _describe_deviation((row[max_col] - stats[max_col]["mean"]) / stats[max_col]["std"])
                    avg_max       = _format_value(stats[max_col]["mean"], max_col)
                    reason = f"The most striking value in this record is the {readable_max.lower()} ({formatted_max}), which is {sev} compared to the dataset average of {avg_max}."
                    
                    if sec_col and sec_z > 1.5:
                        readable_sec  = _humanize_feature_name(sec_col)
                        formatted_sec = _format_value(row[sec_col], sec_col)
                        sev2, _       = _describe_deviation((row[sec_col] - stats[sec_col]["mean"]) / stats[sec_col]["std"])
                        reason += f" The {readable_sec.lower()} ({formatted_sec}) is also {sev2}, which combined with the above pushed this record past the detection threshold."
                    reasons_list[idx] = reason
                else:
                    reasons_list[idx] = f"{subject} doesn't have one obvious red flag, but the combination of several values together created a pattern the model hasn't seen before."

    df = df.with_columns(pl.Series(name="AI_Reason", values=reasons_list))

    if "logic_violation" in df.columns:
        df = df.drop("logic_violation")

    raw_parquet_path = f"{session_dir}/raw_data.parquet"
    df.write_parquet(raw_parquet_path)

    try:
        schema_data = {"columns": df.columns, "dtypes": [str(t) for t in df.dtypes], "row_count": len(df)}
        meta_path = os.path.join(_session_dir(session_id), "metadata.json")
        with open(meta_path, "w") as f:
            json.dump(schema_data, f)
    except Exception:
        pass

    drift_report: dict = {}
    baseline_path = os.path.normpath(os.path.join(session_dir, "..", "baseline_stats.json"))
    try:
        from scipy.stats import ks_2samp  
        current_stats: dict[str, list] = {col: pandas_df[col].dropna().tolist() for col in original_numeric[:10]}
        if os.path.exists(baseline_path):
            with open(baseline_path) as bf:
                baseline_stats = json.load(bf)
            drifted_features = []
            for col, vals in current_stats.items():
                if col in baseline_stats and len(vals) >= 30 and len(baseline_stats[col]) >= 30:
                    stat, p_val = ks_2samp(baseline_stats[col], vals)
                    if p_val < 0.05:
                        drifted_features.append({"feature": col, "ks_stat": round(stat, 4), "p_value": round(p_val, 6)})
            drift_report = {"drifted_features": drifted_features, "baseline_present": True}
        else:
            with open(baseline_path, "w") as bf:
                json.dump(current_stats, bf)
            drift_report = {"drifted_features": [], "baseline_present": False}
    except Exception:
        pass

    feedback_path = os.path.normpath(os.path.join(session_dir, "..", "feedback_log.jsonl"))
    if not os.path.exists(feedback_path):
        try:
            from pathlib import Path
            Path(feedback_path).touch(exist_ok=True)
        except Exception:
            pass

    col_str = " ".join(df.columns).lower()
    text_heavy = len(cat_cols) >= len(numeric_cols) and len(cat_cols) > 0
    is_large = len(pandas_df) > 2_000
    has_time = len(time_cols) > 0

    if text_heavy or any(kw in col_str for kw in ["review", "text", "description", "summary", "comment"]):
        recommended_cleaning = "mask"
        cleaning_rationale = "Text-heavy dataset detected. We recommend 'Masking' to safely redact anomalous strings."
    elif any(kw in col_str for kw in ["amount", "transaction", "fraud", "price", "payment", "bank", "credit"]):
        recommended_cleaning = "quarantine"
        cleaning_rationale = "Financial or Security data detected. 'Quarantine' is strictly recommended to isolate threats."
    elif has_time and any(kw in col_str for kw in ["sensor", "temp", "reading", "humidity", "metric", "iot"]):
        recommended_cleaning = "impute"
        cleaning_rationale = "Sequential telemetry/sensor data detected. 'Predictive KNN Imputation' is recommended."
    elif any(kw in col_str for kw in ["age", "passenger", "survived", "income", "gender", "patient", "blood", "disease", "fare"]):
        recommended_cleaning = "impute"
        cleaning_rationale = "Demographic data detected. 'Contextual Imputation' is recommended to salvage rows."
    elif is_large and len(numeric_cols) > 3:
        recommended_cleaning = "winsorize"
        cleaning_rationale = "Large-scale numerical dataset detected. 'Winsorization' is recommended to cap extreme statistical outliers."
    else:
        recommended_cleaning = "quarantine"
        cleaning_rationale = "Generic dataset detected. 'Quarantine' is the safest default action to isolate anomalies."

    return {
        "status": "success",
        "session_id": session_id,
        "total_rows": len(df),
        "anomaly_count": sum(is_anomaly),
        "algorithm_used": algorithm,
        "recommendation": recommendation,
        "applied_rules": applied_rules,  
        "recommended_cleaning": recommended_cleaning,
        "cleaning_rationale": cleaning_rationale,
        "parquet_path": raw_parquet_path,
        "drift_report": drift_report,
    }