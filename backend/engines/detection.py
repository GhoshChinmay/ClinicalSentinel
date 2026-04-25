"""
DataSentinel — Anomaly Detection Engine
Isolation Forest anomaly detection with Velocity Engine, Threat Scoring,
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

# Keywords that indicate the column is a velocity / sequence feature
_VELOCITY_KWS = ("velocity_", "lstm_", "lof_", "ecod_", "nlp_pc")


def _humanize_feature_name(col: str) -> str:
    """
    Convert an internal column name to a readable label.

    Examples
    --------
    ``"transaction_amount_entity_z"``  →  ``"Transaction Amount"``
    ``"velocity_24h_sum"``             →  ``"24-hour Activity Volume"``
    ``"lstm_anomaly_score"``           →  ``"Behavioural Pattern Score"``
    ``"merchant_id_freq"``             →  ``"Merchant"``
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
    """
    Translate a Z-score into a plain-English severity word and direction phrase.

    Returns
    -------
    (severity, direction_phrase)
        e.g. ("exceptionally high", "well above what is normally seen")
    """
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
    """
    Format a raw value with intuitive units where possible.

    Examples
    --------
    ``(892.5, "transaction_amount")`` → ``"$892.50"``
    ``(0.94, "fraud_probability")``   → ``"94%"``
    ``(3, "item_count")``             → ``"3"``
    """
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "unknown"

    col_lower = col.lower()

    # Currency columns
    if any(kw in col_lower for kw in ("amount", "price", "balance", "total", "cost", "payment", "fare", "revenue", "salary", "income")):
        try:
            return f"${float(val):,.2f}"
        except (ValueError, TypeError):
            pass

    # Percentage / probability columns
    if any(kw in col_lower for kw in ("prob", "pct", "percent", "ratio", "rate", "score")) and 0 <= float(val) <= 1:
        try:
            return f"{float(val) * 100:.1f}%"
        except (ValueError, TypeError):
            pass

    # Age / duration in whole numbers
    if any(kw in col_lower for kw in ("age", "days", "hours", "minutes", "years")):
        try:
            return str(int(round(float(val))))
        except (ValueError, TypeError):
            pass

    # Generic float
    if isinstance(val, float):
        return f"{val:,.2f}" if abs(val) >= 1 else f"{val:.4f}"

    return str(val)


def _detect_domain(col_str: str) -> str:
    """
    Return a short domain tag based on column names.
    Used to select domain-appropriate language in narratives.
    """
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


# Domain-specific subject pronouns used in narrative sentences
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
    """
    Rewrite a raw logic gate violation message into plain English.

    The logic gate produces messages like:
        "amount > 0 violated: amount=-50.0"
    This function turns that into a human sentence.
    """
    if not raw_violation or not isinstance(raw_violation, str):
        return "A data integrity rule was broken — the values in this record are logically inconsistent."

    raw = raw_violation.strip()

    # Pattern: "<rule_expr> violated: <field>=<value>"
    # Try to extract a clean message
    if "violated:" in raw.lower():
        parts = raw.lower().split("violated:", 1)
        rule_part = parts[0].strip().rstrip(".")
        detail_part = parts[1].strip() if len(parts) > 1 else ""

        # Build a readable rule description
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

    # Fallback: clean it up and wrap it
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
    """
    Run the full anomaly detection pipeline.

    Parameters
    ----------
    file_path : str, optional
        Path to a CSV file to load.  Ignored when ``df`` is supplied.
    session_id : str, optional
        Reuse an existing session; a new UUID is generated when omitted.
    algorithm : str
        Detection back-end.  Supported values:
        ``"isolation_forest"`` (default), ``"lof"``, ``"ecod"``.
        Unknown values fall back to ``"isolation_forest"`` with a warning.
    df : pl.DataFrame, optional
        Pre-loaded Polars DataFrame.  Takes priority over ``file_path``.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    session_dir = _session_dir(session_id)

    # Normalise algorithm name and warn on unknown values
    _supported_algorithms = {"isolation_forest", "lof", "ecod"}
    algorithm = algorithm.lower().strip()
    if algorithm not in _supported_algorithms:
        logger.warning(
            "Unknown algorithm '%s'. Falling back to 'isolation_forest'.", algorithm
        )
        algorithm = "isolation_forest"

    # -----------------------------------------------------------------
    # DATA LOADING (skip when a DataFrame is already provided)
    # -----------------------------------------------------------------
    if df is None:
        try:
            df = pl.read_csv(file_path, infer_schema_length=1_000_000)
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
                    "error": (
                        f"Fatal Read Error. Both engines failed to parse the CSV: {inner_e}"
                    )
                }

    pre_dedup = len(df)
    df = df.unique()
    logger.info("Dedup complete: %d → %d rows.", pre_dedup, len(df))

    # -----------------------------------------------------------------
    # STAGE 1: THE NEURO-SYMBOLIC LOGIC GATE (Semantic Context)
    # -----------------------------------------------------------------
    df, applied_rules = apply_logic_gate(df)

    # -----------------------------------------------------------------
    # STAGE 2: THE VELOCITY ENGINE (Time-Series Context)
    # -----------------------------------------------------------------
    time_cols = [
        c
        for c in df.columns
        if "date" in c.lower() or "time" in c.lower() or "timestamp" in c.lower()
    ]
    entity_keywords = [
        "user", "account", "customer", "merchant",
        "employee", "sender", "client", "patient",
    ]
    id_cols = [
        c
        for c in df.columns
        if "id" in c.lower() and any(kw in c.lower() for kw in entity_keywords)
    ]

    velocity_cols_added: list[str] = []
    lstm_score_available = False

    if time_cols and id_cols:
        t_col = time_cols[0]
        i_col = id_cols[0]

        logger.info(
            "Time-Series detected. Tracking velocity for '%s' over '%s'...",
            i_col, t_col,
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
                        candidate = df.with_columns(
                            pl.col(t_col).str.strptime(
                                pl.Datetime, format=fmt, strict=False
                            )
                        )
                        if candidate[t_col].null_count() / len(candidate) < 0.5:
                            df = candidate
                            parsed = candidate
                            logger.info("Parsed '%s' with format '%s'.", t_col, fmt)
                            break
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
                "amount", "value", "price", "total",
                "balance", "sum", "cost", "payment",
            ]
            smart_picks = [
                c
                for c in numeric_cols_for_velocity
                if any(kw in c.lower() for kw in amount_keywords)
            ]
            track_col = (
                smart_picks[0]
                if smart_picks
                else (numeric_cols_for_velocity[0] if numeric_cols_for_velocity else None)
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
                logger.info("Velocity tracking successfully generated for '%s'.", track_col)

                # ---------------------------------------------------
                # LSTM AUTOENCODER: Sequential anomaly scoring
                # Learns normal entity sequences; flags high reconstruction error.
                # The score is stored on ``df`` here and merged into
                # ``encoded_df`` after it is built so IF/LOF can use it.
                # ---------------------------------------------------
                try:
                    import tensorflow as tf  # type: ignore
                    from tensorflow import keras  # type: ignore

                    logger.info("Fitting LSTM Autoencoder on entity sequences...")
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

                        # Map errors back to original positional indices in seq_df
                        lstm_scores_arr = np.zeros(len(df))
                        seq_df_index_list = seq_df.index.tolist()
                        for k, orig_idx in enumerate(seq_index_map):
                            try:
                                pos_in_df = seq_df_index_list.index(orig_idx)
                                lstm_scores_arr[pos_in_df] = max(
                                    lstm_scores_arr[pos_in_df], recon_errors[k]
                                )
                            except ValueError:
                                pass

                        df = df.with_columns(
                            pl.Series(name="lstm_anomaly_score", values=lstm_scores_arr.tolist())
                        )
                        lstm_score_available = True
                        logger.info("LSTM Autoencoder scoring complete.")
                    else:
                        logger.info("LSTM skipped — not enough sequences (need ≥20).")
                except ImportError:
                    logger.info("LSTM Autoencoder skipped — TensorFlow not installed.")
                except Exception as e:
                    logger.warning("LSTM Autoencoder failed: %s", e)
            else:
                logger.info(
                    "Velocity Engine skipped — no numeric columns found for tracking."
                )
        except Exception as e:
            logger.warning("Velocity Engine skipped due to parsing error: %s", e)

    # -----------------------------------------------------------------
    # FEATURE ENGINEERING
    # -----------------------------------------------------------------
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

    # Merge LSTM score into encoded_df so IF/LOF can use it as a feature
    if lstm_score_available and "lstm_anomaly_score" in pandas_df.columns:
        encoded_df["lstm_anomaly_score"] = pandas_df["lstm_anomaly_score"].fillna(0).values
        logger.info("LSTM anomaly score merged into feature matrix.")

    # -----------------------------------------------------------------
    # ENTITY-RELATIVE Z-SCORE FEATURES
    # Scores each row against its own entity history to reduce false
    # positives on high-volume entities (power users, busy merchants).
    # -----------------------------------------------------------------
    entity_zscore_cols_added: list[str] = []
    if id_cols:
        i_col_enc = id_cols[0]
        if i_col_enc in pandas_df.columns:
            amount_kws = [
                "amount", "value", "price", "total",
                "balance", "sum", "cost", "payment",
            ]
            entity_target_cols = [
                c for c in numeric_cols
                if any(kw in c.lower() for kw in amount_kws)
                and c not in ("velocity_24h_sum", "velocity_1h_count")
            ][:3]  # cap at 3 to avoid feature explosion

            if entity_target_cols:
                entity_groups = pandas_df.groupby(i_col_enc)
                for col in entity_target_cols:
                    entity_mean = entity_groups[col].transform("mean")
                    entity_std = entity_groups[col].transform("std").fillna(1).replace(0, 1)
                    z_col = f"{col}_entity_z"
                    encoded_df[z_col] = ((pandas_df[col] - entity_mean) / entity_std).fillna(0)
                    entity_zscore_cols_added.append(z_col)
                logger.info("Entity-relative Z-scores added for: %s", entity_target_cols)

    # -----------------------------------------------------------------
    # STAGE 2.5: ECOD (Empirical CDF Outlier Detection)
    # Non-parametric distributional extremity — enriches IF feature space.
    # -----------------------------------------------------------------
    ecod_score_added = False
    if ECOD_AVAILABLE and len(encoded_df) > 0:
        try:
            logger.info("Running ECOD distributional outlier scoring...")
            # Drop zero-variance columns — ECOD's log arithmetic throws on them.
            ecod_safe_df = encoded_df.loc[:, encoded_df.nunique() > 1]

            if not ecod_safe_df.empty and len(ecod_safe_df.columns) > 0:
                ecod = ECOD()
                ecod.fit(ecod_safe_df.values)
                encoded_df = encoded_df.copy()
                encoded_df["ecod_score"] = ecod.decision_scores_
                ecod_score_added = True
                logger.info("ECOD scores added as feature column.")
            else:
                logger.info("ECOD skipped — no variable features found.")
        except Exception as e:
            logger.warning("ECOD scoring failed: %s", e)
    elif not ECOD_AVAILABLE:
        logger.info("ECOD unavailable — install pyod to enable. Skipping.")

    # -----------------------------------------------------------------
    # STAGE 3: THE AI DETECTION ENGINE
    # Route to the algorithm requested by the caller.
    # -----------------------------------------------------------------
    _algo_label_parts = []
    if ecod_score_added:
        _algo_label_parts.append("ECOD-enriched")

    if algorithm == "ecod" and ecod_score_added:
        # ECOD-only mode: use ecod_score directly as the anomaly signal
        recommendation = "ECOD-only (Empirical CDF)"
        inverted_scores = encoded_df["ecod_score"].values if "ecod_score" in encoded_df else np.zeros(len(encoded_df))
        model = None
        model_fitted = bool(ecod_score_added)
    elif algorithm == "lof":
        recommendation = "LOF-only (Local Outlier Factor)"
        model = None
        model_fitted = False
        inverted_scores = np.zeros(len(encoded_df))  # filled by the LOF block below
    else:
        # Default: Isolation Forest (optionally enriched by ECOD/LSTM features)
        _algo_label_parts.append("Isolation Forest + LOF Ensemble")
        recommendation = " + ".join(_algo_label_parts) + " (Z-Score Scaled)"

    # BASELINE PROTECTOR: exclude Neuro-Symbolic violations from IF training
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
        logger.warning("No clean training data available. Falling back to full dataset.")
        train_df = encoded_df

    # Dynamic sigma multiplier (shared by IF and LOF threshold derivation)
    col_str_check = " ".join(pandas_df.columns).lower()
    _finance_kws = ["amount", "transaction", "fraud", "payment", "bank", "credit", "merchant", "card"]
    _demo_kws = ["age", "passenger", "income", "gender", "patient", "blood", "disease", "fare"]
    if any(kw in col_str_check for kw in _finance_kws):
        _sigma_mult = 1.2
        logger.info("Dynamic threshold: finance domain → %.1fσ (tight).", _sigma_mult)
    elif any(kw in col_str_check for kw in _demo_kws):
        _sigma_mult = 2.0
        logger.info("Dynamic threshold: demographic domain → %.1fσ (loose).", _sigma_mult)
    else:
        _sigma_mult = 1.5
        logger.info("Dynamic threshold: generic domain → %.1fσ (default).", _sigma_mult)

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
        # LOF-only path: fit + score here; the LOF block below will also run
        # but in novelty=True mode re-using the same clean training set.
        threshold = 1.0  # placeholder; real threshold set in LOF block
    elif algorithm == "ecod" and ecod_score_added:
        mean_w = np.mean(inverted_scores)
        std_w = np.std(inverted_scores)
        threshold = mean_w + (_sigma_mult * std_w)
        model_fitted = True
    else:
        if len(encoded_df) > 0:
            logger.warning("Dataset is empty or algorithm route produced no model. Skipping detection.")
        inverted_scores = np.zeros(len(encoded_df))
        threshold = 1.0

    # Base flagging
    is_anomaly: list[bool] = []
    if len(inverted_scores) > 0:
        for i, s in enumerate(inverted_scores):
            has_logic_error = (
                "logic_violation" in pandas_df.columns
                and pd.notna(pandas_df.at[i, "logic_violation"])
            )
            is_anomaly.append(bool((model_fitted and s > threshold) or has_logic_error))
    # else: remains empty; safety-extend happens after LOF block

    # -----------------------------------------------------------------
    # STAGE 3.5: LOCAL OUTLIER FACTOR (LOF)
    # Catches cluster-relative anomalies that IF misses globally.
    # Uses the same dynamic sigma multiplier as the IF threshold.
    # -----------------------------------------------------------------
    lof_scores = np.zeros(len(encoded_df))
    if len(clean_encoded_df) > 0 and algorithm in ("isolation_forest", "ecod", "lof"):
        try:
            logger.info("Running LOF for cluster-relative outlier detection...")
            lof = LocalOutlierFactor(n_neighbors=20, novelty=True, n_jobs=-1)
            lof.fit(clean_encoded_df)
            lof_raw = lof.score_samples(encoded_df)
            lof_scores = -lof_raw

            lof_mean = np.mean(lof_scores)
            lof_std = np.std(lof_scores)
            lof_threshold = lof_mean + (_sigma_mult * lof_std)

            if algorithm == "lof":
                # LOF-only: rebuild is_anomaly entirely from LOF signal
                model_fitted = True
                inverted_scores = lof_scores
                threshold = lof_threshold
                is_anomaly = []
                for i, s in enumerate(lof_scores):
                    has_logic_error = (
                        "logic_violation" in pandas_df.columns
                        and pd.notna(pandas_df.at[i, "logic_violation"])
                    )
                    is_anomaly.append(bool(s > lof_threshold or has_logic_error))
            else:
                # OR-combine: flag if IF or LOF considers it anomalous
                for i in range(len(is_anomaly)):
                    has_logic_error = (
                        "logic_violation" in pandas_df.columns
                        and pd.notna(pandas_df.at[i, "logic_violation"])
                    )
                    if not is_anomaly[i] and not has_logic_error:
                        if lof_scores[i] > lof_threshold:
                            is_anomaly[i] = True

            logger.info("LOF scoring complete — OR-combined with primary model results.")
        except Exception as e:
            logger.warning("LOF scoring failed: %s", e)

    df = df.with_columns(pl.Series(name="lof_score", values=lof_scores.tolist()))

    # =========================================================
    # THE ANOMALY OVERLOAD SHIELD
    # =========================================================

    # 1. SHIELD: Bypass broken logic gate rules (>90 % of rows flagged)
    logic_flags = sum(
        1
        for i in range(len(pandas_df))
        if "logic_violation" in pandas_df.columns
        and pd.notna(pandas_df.at[i, "logic_violation"])
    )
    if len(pandas_df) > 0 and (logic_flags / len(pandas_df)) > 0.90:
        logger.warning(
            "Logic Gate blocked >90%% of rows! Rules are incompatible. Bypassing Logic Gate entirely."
        )
        if "logic_violation" in pandas_df.columns:
            pandas_df["logic_violation"] = np.nan
        is_anomaly = [
            bool(model_fitted and s > threshold)
            for s in inverted_scores
        ]

    # 2. SHIELD: Cap statistical anomalies — domain-configurable
    _cap_kws_finance = ["amount", "transaction", "fraud", "payment", "bank", "credit", "merchant", "card"]
    _cap_kws_demo = ["age", "passenger", "income", "gender", "patient", "blood", "disease", "fare"]
    _col_check = " ".join(pandas_df.columns).lower()
    if any(kw in _col_check for kw in _cap_kws_finance):
        _anomaly_cap = 0.10
    elif any(kw in _col_check for kw in _cap_kws_demo):
        _anomaly_cap = 0.20
    else:
        _anomaly_cap = 0.15

    stat_anomaly_count = sum(
        1
        for i, x in enumerate(is_anomaly)
        if x
        and not (
            "logic_violation" in pandas_df.columns
            and pd.notna(pandas_df.at[i, "logic_violation"])
        )
    )
    if len(pandas_df) > 0 and stat_anomaly_count / len(pandas_df) > _anomaly_cap:
        logger.warning(
            "Statistical Anomaly Overload. Forcing a %.0f%% cap.", _anomaly_cap * 100
        )
        if len(inverted_scores) > 0:
            top_threshold = np.percentile(inverted_scores, (1 - _anomaly_cap) * 100)
            for i, x in enumerate(is_anomaly):
                if x and not (
                    "logic_violation" in pandas_df.columns
                    and pd.notna(pandas_df.at[i, "logic_violation"])
                ):
                    if inverted_scores[i] < top_threshold:
                        is_anomaly[i] = False

    # Safety-extend: guard against empty dataset edge case
    if len(is_anomaly) < len(df):
        is_anomaly.extend([False] * (len(df) - len(is_anomaly)))

    df = df.with_columns(pl.Series(name="is_anomaly", values=is_anomaly))

    # -----------------------------------------------------------------
    # STAGE 4: SHAP EXPLAINABILITY LAYER
    # Capped at _SHAP_MAX_ROWS to avoid multi-minute hangs on large sets.
    # -----------------------------------------------------------------
    shap_payloads = ["[]"] * len(pandas_df)
    try:
        if model_fitted and model is not None:
            logger.info("Computing SHAP values for anomaly attribution...")
            explainer = shap.TreeExplainer(model)

            stat_anomaly_indices = [
                i
                for i, x in enumerate(is_anomaly)
                if x
                and not (
                    "logic_violation" in pandas_df.columns
                    and pd.notna(pandas_df.at[i, "logic_violation"])
                )
            ]

            # Cap to avoid hanging on large flagged sets
            if len(stat_anomaly_indices) > _SHAP_MAX_ROWS:
                logger.info(
                    "SHAP capped at %d rows (total anomalies: %d).",
                    _SHAP_MAX_ROWS, len(stat_anomaly_indices),
                )
                stat_anomaly_indices = stat_anomaly_indices[:_SHAP_MAX_ROWS]

            feature_names = encoded_df.columns.tolist()

            if stat_anomaly_indices:
                anom_encoded_df = encoded_df.iloc[stat_anomaly_indices]
                shap_vals = explainer.shap_values(anom_encoded_df)

                for j, orig_idx in enumerate(stat_anomaly_indices):
                    row_shap = shap_vals[j]
                    top_indices = np.argsort(np.abs(row_shap))[-3:][::-1]
                    contributions = [
                        {"feature": feature_names[idx], "impact": float(row_shap[idx])}
                        for idx in top_indices
                    ]
                    shap_payloads[orig_idx] = json.dumps(contributions)

        df = df.with_columns(pl.Series(name="SHAP_Payload", values=shap_payloads))
    except Exception as e:
        logger.warning("SHAP attribution failed: %s", e)
        df = df.with_columns(
            pl.Series(name="SHAP_Payload", values=["[]"] * len(pandas_df))
        )

    # -----------------------------------------------------------------
    # STAGE 4.5: COUNTERFACTUAL EXPLANATIONS (DiCE)
    # Answers "what would need to change for this row to NOT be anomalous?"
    # -----------------------------------------------------------------
    counterfactual_payloads = ["{}"] * len(pandas_df)
    try:
        import dice_ml  # type: ignore

        if model_fitted and model is not None and any(is_anomaly):
            logger.info("Generating DiCE counterfactual explanations...")

            pseudo_labels = [int(x) for x in is_anomaly]
            cf_df = encoded_df.copy().astype(float)
            cf_df["_target"] = pseudo_labels

            dice_data = dice_ml.Data(
                dataframe=cf_df,
                continuous_features=cf_df.drop(columns=["_target"]).columns.tolist(),
                outcome_name="_target",
            )

            class _IFWrapper:
                """Thin sklearn-compatible wrapper around IsolationForest."""
                def __init__(self, m: IsolationForest, thresh: float) -> None:
                    self.m = m
                    self.thresh = thresh

                def predict(self, X) -> np.ndarray:
                    # Accept both DataFrame and ndarray
                    arr = X.values if hasattr(X, "values") else np.asarray(X)
                    s = -self.m.decision_function(arr)
                    return (s > self.thresh).astype(int)

            wrapped = _IFWrapper(model, threshold)
            dice_model = dice_ml.Model(model=wrapped, backend="sklearn")
            exp = dice_ml.Dice(dice_data, dice_model, method="random")

            stat_anom_idxs = [
                i for i, x in enumerate(is_anomaly)
                if x and not (
                    "logic_violation" in pandas_df.columns
                    and pd.notna(pandas_df.at[i, "logic_violation"])
                )
            ][:20]

            for orig_idx in stat_anom_idxs:
                try:
                    query = encoded_df.iloc[[orig_idx]].astype(float)
                    cf_result = exp.generate_counterfactuals(
                        query, total_CFs=1, desired_class="opposite", verbose=False
                    )
                    cf_dict = cf_result.cf_examples_list[0].final_cfs_df.iloc[0].to_dict()
                    original_row = encoded_df.iloc[orig_idx].to_dict()
                    changes = {
                        k: {
                            "from": round(float(original_row[k]), 4),
                            "to": round(float(v), 4),
                        }
                        for k, v in cf_dict.items()
                        if k != "_target"
                        and abs(float(v) - float(original_row.get(k, 0))) > 1e-4
                    }
                    counterfactual_payloads[orig_idx] = json.dumps(changes)
                except Exception:
                    pass  # silently skip rows where CF generation fails

            logger.info(
                "DiCE counterfactuals generated for up to %d anomalies.",
                len(stat_anom_idxs),
            )

        df = df.with_columns(
            pl.Series(name="Counterfactual_Payload", values=counterfactual_payloads)
        )
    except ImportError:
        logger.info(
            "DiCE not installed — counterfactual explanations skipped. "
            "pip install dice-ml to enable."
        )
        df = df.with_columns(
            pl.Series(name="Counterfactual_Payload", values=counterfactual_payloads)
        )
    except Exception as e:
        logger.warning("DiCE counterfactual generation failed: %s", e)
        df = df.with_columns(
            pl.Series(name="Counterfactual_Payload", values=counterfactual_payloads)
        )

    # -----------------------------------------------------------------
    # STAGE 5: TIER 2 THREAT ENGINE (Scoring)
    # -----------------------------------------------------------------
    if "Class" in pandas_df.columns:
        try:
            X = (
                encoded_df.drop(columns=["Class"])
                if "Class" in encoded_df.columns
                else encoded_df
            )
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
                classifier = XGBClassifier(
                    scale_pos_weight=scale_pos,
                    eval_metric="aucpr",
                    random_state=42,
                    verbosity=0,
                    use_label_encoder=False,
                )
                logger.info("Using XGBClassifier (scale_pos_weight=%.1f).", scale_pos)
            else:
                classifier = HistGradientBoostingClassifier(
                    class_weight="balanced", random_state=42
                )
                logger.info("XGBoost unavailable — using HistGradientBoostingClassifier.")

            classifier.fit(X_train, y_train)
            probabilities = classifier.predict_proba(X)[:, 1]
            threat_scores = []
            for i, p in enumerate(probabilities):
                has_logic_error = (
                    "logic_violation" in pandas_df.columns
                    and pd.notna(pandas_df.at[i, "logic_violation"])
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
            min_s = inverted_scores.min() if len(inverted_scores) > 0 else 0
            max_s = inverted_scores.max() if len(inverted_scores) > 0 else 0

            threat_scores = []
            if max_s > min_s:
                for i, s in enumerate(inverted_scores):
                    has_logic_error = (
                        "logic_violation" in pandas_df.columns
                        and pd.notna(pandas_df.at[i, "logic_violation"])
                    )
                    if has_logic_error:
                        threat_scores.append(100.0)
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
                        score = (((s - min_s) / range_norm) * 40) if range_norm > 0 else 0
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

    # -----------------------------------------------------------------
    # STAGE 6: NARRATIVE SYNTHESIS (Humanized AI Reason Generator)
    # -----------------------------------------------------------------
    logger.info("Starting Narrative Synthesis for AI Reasoning...")

    engineered_suffixes = ("_length", "_digit_ratio", "_upper_ratio", "_special_ratio")
    engineered_prefixes = ("nlp_pc",)
    velocity_col_names = set(velocity_cols_added)
    entity_z_col_names = set(entity_zscore_cols_added)

    original_numeric = [
        c
        for c in numeric_cols
        if not c.endswith(engineered_suffixes)
        and not any(c.startswith(p) for p in engineered_prefixes)
        and c not in velocity_col_names
        and c not in entity_z_col_names
        and c != "lstm_anomaly_score"
    ]

    # Detect domain once for the whole dataset so language adapts consistently
    _all_cols_str = " ".join(pandas_df.columns).lower()
    domain = _detect_domain(_all_cols_str)
    subject = _DOMAIN_SUBJECT[domain]       # e.g. "This transaction"
    entity  = _DOMAIN_ENTITY[domain]        # e.g. "account"

    reasons_list = [""] * len(pandas_df)

    if any(is_anomaly):
        # Pre-compute column stats once
        stats: dict[str, dict] = {}
        for col in original_numeric:
            col_mean = pandas_df[col].mean()
            col_std  = pandas_df[col].std()
            stats[col] = {
                "mean": col_mean if pd.notna(col_mean) else 0.0,
                "std":  col_std  if pd.notna(col_std)  else 0.0,
            }

        # Pre-compute rare categorical values (< 5 % frequency)
        rare_cats: dict[str, list] = {}
        for col in cat_cols:
            if len(pandas_df) > 0 and pandas_df[col].nunique() / len(pandas_df) < 0.3:
                counts = pandas_df[col].value_counts(normalize=True)
                rare_cats[col] = counts[counts < 0.05].index.tolist()

        # Parse SHAP payloads once for all anomalies
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

        # ------------------------------------------------------------------
        # Also pre-compute entity Z-score data for richer "vs own history"
        # language when entity columns are present.
        # ------------------------------------------------------------------
        entity_col_in_data = id_cols[0] if id_cols else None

        for idx in anomaly_indices:
            row = pandas_df.iloc[idx]
            parts: list[str] = []   # sentence fragments — joined at the end

            # ---------------------------------------------------------------
            # PATH A: Logic Gate violation → plain English data-integrity note
            # ---------------------------------------------------------------
            if "logic_violation" in pandas_df.columns and pd.notna(row.get("logic_violation")):
                reasons_list[idx] = _build_logic_violation_narrative(row["logic_violation"])
                continue

            # ---------------------------------------------------------------
            # PATH B: SHAP-driven narrative (model explained this row)
            # ---------------------------------------------------------------
            if idx in parsed_shap and parsed_shap[idx]:
                shap_items = parsed_shap[idx]
                top_feat   = shap_items[0]["feature"]
                top_impact = shap_items[0]["impact"]

                # Clean the feature name — strip internal suffixes
                orig_feat = top_feat
                for suf in _STRIP_SUFFIXES:
                    if orig_feat.endswith(suf):
                        orig_feat = orig_feat[: -len(suf)]
                        break

                readable_feat = _humanize_feature_name(orig_feat)

                # Retrieve and format the raw value
                raw_val = row.get(orig_feat, row.get(top_feat))
                formatted_val = _format_value(raw_val, orig_feat)

                # ---- Primary sentence ----

                # Special case: velocity feature
                if top_feat in velocity_col_names or orig_feat in velocity_col_names:
                    vel_24h = row.get("velocity_24h_sum")
                    vel_1h  = row.get("velocity_1h_count")
                    if vel_1h is not None and pd.notna(vel_1h) and float(vel_1h) > 1:
                        parts.append(
                            f"{subject} is part of a burst of {int(vel_1h)} rapid "
                            f"transactions from the same {entity} within a single hour — "
                            f"a pace that stands out as highly unusual."
                        )
                    elif vel_24h is not None and pd.notna(vel_24h):
                        parts.append(
                            f"The total activity from this {entity} over the past 24 hours "
                            f"({_format_value(vel_24h, 'amount')}) is unusually high "
                            f"and well above what is normally seen in a single day."
                        )
                    else:
                        parts.append(
                            f"{subject} shows an abnormal spike in activity over a short "
                            f"window of time, which is a common indicator of automated or "
                            f"suspicious behaviour."
                        )

                # Special case: LSTM behavioural anomaly
                elif top_feat.startswith("lstm_") or orig_feat.startswith("lstm_"):
                    parts.append(
                        f"The recent sequence of activity from this {entity} breaks away "
                        f"from its own established pattern. The AI detected that the order "
                        f"and rhythm of recent events no longer match how this {entity} "
                        f"normally behaves — even if individual values look ordinary on their own."
                    )

                # Special case: entity Z-score (same account comparison)
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
                        parts.append(
                            f"The {base_readable.lower()} for this entry ({base_val}) is "
                            f"far outside what this specific {entity} normally does — "
                            f"their own historical average is around {avg_readable}. "
                            f"This gap from their own baseline is what raised the alert."
                        )
                    else:
                        parts.append(
                            f"The {base_readable.lower()} here ({base_val}) is much higher "
                            f"than this {entity} typically records, which is what drew the "
                            f"system's attention."
                        )

                # Standard numeric feature with Z-score context
                elif orig_feat in stats and stats[orig_feat]["std"] > 0:
                    raw_feat_val = row.get(orig_feat)
                    if raw_feat_val is None or (hasattr(raw_feat_val, '__float__') is False and not isinstance(raw_feat_val, (int, float))):
                        continue
                    z = (float(raw_feat_val) - stats[orig_feat]["mean"]) / stats[orig_feat]["std"]
                    severity, context_phrase = _describe_deviation(z)
                    avg_readable = _format_value(stats[orig_feat]["mean"], orig_feat)

                    openers = [
                        f"The {readable_feat.lower()} for this record is {formatted_val}, which is {severity} — {context_phrase}. The typical value across the dataset is around {avg_readable}.",
                        f"What stands out most is the {readable_feat.lower()}: {formatted_val}. Compared to the usual figure of {avg_readable}, this is {severity} and {context_phrase}.",
                        f"{subject} was flagged primarily because its {readable_feat.lower()} ({formatted_val}) is {severity}, sitting {context_phrase}. Most records in this dataset show values near {avg_readable}.",
                        f"A {readable_feat.lower()} of {formatted_val} is {severity} for this dataset — {context_phrase}. The average across all records is {avg_readable}.",
                    ]
                    parts.append(random.choice(openers))

                # Rare categorical value
                elif orig_feat in rare_cats and str(raw_val) in rare_cats.get(orig_feat, []):
                    parts.append(
                        f"The value '{raw_val}' in the {readable_feat.lower()} field is "
                        f"extremely uncommon — it appears in fewer than 5% of all records. "
                        f"Rare categories like this can indicate unusual circumstances or "
                        f"data that doesn't match standard patterns."
                    )

                # Fallback for categorical / unquantifiable primary feature
                else:
                    parts.append(
                        f"{subject} stood out because of an unusual combination involving "
                        f"{readable_feat.lower()} ({formatted_val}), which the model "
                        f"identified as behaving differently from the rest of the data."
                    )

                # ---- Secondary contributing factor ----
                if len(shap_items) > 1 and abs(shap_items[1]["impact"]) > abs(top_impact) * 0.25:
                    sec_feat = shap_items[1]["feature"]
                    sec_orig = sec_feat
                    for suf in _STRIP_SUFFIXES:
                        if sec_orig.endswith(suf):
                            sec_orig = sec_orig[: -len(suf)]
                            break

                    sec_readable  = _humanize_feature_name(sec_orig)
                    sec_raw_val   = row.get(sec_orig, row.get(sec_feat))
                    sec_formatted = _format_value(sec_raw_val, sec_orig)

                    # Build context for secondary feature
                    if sec_orig in stats and stats[sec_orig]["std"] > 0:
                        z2 = (row[sec_orig] - stats[sec_orig]["mean"]) / stats[sec_orig]["std"]
                        sev2, ctx2 = _describe_deviation(z2)
                        sec_parts = [
                            f"On top of that, the {sec_readable.lower()} ({sec_formatted}) is also {sev2}, adding to the concern.",
                            f"This is compounded by the {sec_readable.lower()}, which at {sec_formatted} is also {sev2} — {ctx2}.",
                            f"The {sec_readable.lower()} ({sec_formatted}) is an additional signal: it too is {sev2} for this dataset.",
                        ]
                    elif sec_orig in rare_cats and str(sec_raw_val) in rare_cats.get(sec_orig, []):
                        sec_parts = [
                            f"The {sec_readable.lower()} field ('{sec_raw_val}') is also an unusual category, rarely seen in this dataset.",
                            f"Adding to this, '{sec_raw_val}' is a very rare value for {sec_readable.lower()}, which reinforces the flag.",
                        ]
                    else:
                        sec_parts = [
                            f"The {sec_readable.lower()} ({sec_formatted}) also deviated from what the model normally expects.",
                            f"A secondary signal came from the {sec_readable.lower()} field ({sec_formatted}), which also looked out of place.",
                        ]
                    parts.append(random.choice(sec_parts))

                # ---- Tertiary factor (only if notably strong) ----
                if len(shap_items) > 2 and abs(shap_items[2]["impact"]) > abs(top_impact) * 0.15:
                    ter_feat    = shap_items[2]["feature"]
                    ter_orig    = ter_feat.replace("_freq", "").replace("_entity_z", "")
                    ter_readable = _humanize_feature_name(ter_orig)
                    parts.append(
                        f"Minor additional signal was detected in {ter_readable.lower()} as well."
                    )

                reasons_list[idx] = " ".join(parts)

            # ---------------------------------------------------------------
            # PATH C: No SHAP — fallback to Z-score sweep across raw columns
            # ---------------------------------------------------------------
            else:
                max_z   = 0.0
                max_col = None
                sec_z   = 0.0
                sec_col = None

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
                    sev, ctx      = _describe_deviation(
                        (row[max_col] - stats[max_col]["mean"]) / stats[max_col]["std"]
                    )
                    avg_max       = _format_value(stats[max_col]["mean"], max_col)

                    openers = [
                        f"The most striking value in this record is the {readable_max.lower()} ({formatted_max}), which is {sev} compared to the dataset average of {avg_max}.",
                        f"{subject} was flagged because its {readable_max.lower()} ({formatted_max}) is {sev} — {ctx}. The typical figure is {avg_max}.",
                        f"Looking at the numbers, the {readable_max.lower()} ({formatted_max}) jumps out as {sev}. Normally this sits around {avg_max}.",
                    ]
                    reason = random.choice(openers)

                    if sec_col and sec_z > 1.5:
                        readable_sec  = _humanize_feature_name(sec_col)
                        formatted_sec = _format_value(row[sec_col], sec_col)
                        sev2, _       = _describe_deviation(
                            (row[sec_col] - stats[sec_col]["mean"]) / stats[sec_col]["std"]
                        )
                        reason += (
                            f" The {readable_sec.lower()} ({formatted_sec}) is also "
                            f"{sev2}, which combined with the above pushed this record "
                            f"past the detection threshold."
                        )

                    reasons_list[idx] = reason

                else:
                    # Truly multi-dimensional — no single dominant field
                    multi_openers = [
                        f"{subject} doesn't have one obvious red flag, but the combination of several values together created a pattern the model hasn't seen before. Each field looks borderline individually, but together they're unusual enough to warrant a closer look.",
                        f"No single value here is dramatically out of range, but the overall profile of this record — when viewed as a whole — is unlike the rest of the dataset. This kind of subtle, multi-field deviation is often harder to spot manually.",
                        f"The model flagged this record based on the relationship between multiple fields rather than any one standout value. The overall data signature is uncommon, even if individual numbers seem reasonable in isolation.",
                    ]
                    reasons_list[idx] = random.choice(multi_openers)

    df = df.with_columns(pl.Series(name="AI_Reason", values=reasons_list))

    # Clean up the internal logic_violation column before saving
    if "logic_violation" in df.columns:
        df = df.drop("logic_violation")

    raw_parquet_path = f"{session_dir}/raw_data.parquet"
    df.write_parquet(raw_parquet_path)

    # Cache schema for LLM queries
    try:
        schema_data = {
            "columns": df.columns,
            "dtypes": [str(t) for t in df.dtypes],
            "row_count": len(df),
        }
        meta_path = os.path.join(_session_dir(session_id), "metadata.json")
        with open(meta_path, "w") as f:
            json.dump(schema_data, f)
    except Exception as e:
        logger.warning("Could not save metadata cache: %s", e)

    # -----------------------------------------------------------------
    # DRIFT DETECTION: Kolmogorov-Smirnov feature monitor
    # -----------------------------------------------------------------
    drift_report: dict = {}
    baseline_path = os.path.normpath(os.path.join(session_dir, "..", "baseline_stats.json"))
    try:
        from scipy.stats import ks_2samp  # type: ignore

        current_stats: dict[str, list] = {
            col: pandas_df[col].dropna().tolist()
            for col in original_numeric[:10]
        }

        if os.path.exists(baseline_path):
            with open(baseline_path) as bf:
                baseline_stats = json.load(bf)
            drifted_features = []
            for col, vals in current_stats.items():
                if (
                    col in baseline_stats
                    and len(vals) >= 30
                    and len(baseline_stats[col]) >= 30
                ):
                    stat, p_val = ks_2samp(baseline_stats[col], vals)
                    if p_val < 0.05:
                        drifted_features.append(
                            {
                                "feature": col,
                                "ks_stat": round(stat, 4),
                                "p_value": round(p_val, 6),
                            }
                        )
            if drifted_features:
                logger.warning(
                    "Drift detected on %d feature(s). Threshold recalibration recommended.",
                    len(drifted_features),
                )
            drift_report = {
                "drifted_features": drifted_features,
                "baseline_present": True,
            }
        else:
            with open(baseline_path, "w") as bf:
                json.dump(current_stats, bf)
            logger.info("No baseline found — current file saved as drift baseline.")
            drift_report = {"drifted_features": [], "baseline_present": False}
    except ImportError:
        logger.info("scipy not available — KS drift detection skipped.")
    except Exception as e:
        logger.warning("Drift detection failed: %s", e)

    # -----------------------------------------------------------------
    # FEEDBACK TABLE: Persistent store for analyst TP/FP reviews
    # Schema: session_id, row_index, label (1=TP / 0=FP),
    #         reviewer, timestamp, anomaly_score
    # -----------------------------------------------------------------
    feedback_path = os.path.normpath(
        os.path.join(session_dir, "..", "feedback_log.jsonl")
    )
    if not os.path.exists(feedback_path):
        try:
            from pathlib import Path
            Path(feedback_path).touch(exist_ok=True)
            logger.info("Feedback log initialised at %s", feedback_path)
        except Exception as e:
            logger.warning("Could not initialise feedback log: %s", e)

    # -----------------------------------------------------------------
    # STAGE 7: SMART CLEANING RECOMMENDATION ENGINE
    # -----------------------------------------------------------------
    col_str = " ".join(df.columns).lower()

    text_heavy = len(cat_cols) >= len(numeric_cols) and len(cat_cols) > 0
    is_large = len(pandas_df) > 2_000
    has_time = len(time_cols) > 0

    if text_heavy or any(
        kw in col_str
        for kw in ["review", "text", "description", "summary", "comment", "feedback"]
    ):
        recommended_cleaning = "mask"
        cleaning_rationale = (
            "Text-heavy dataset detected. We recommend 'Masking' to safely redact "
            "anomalous strings, typos, or bot-generated text with a [REDACTED] tag "
            "without destroying the rest of the row."
        )
    elif any(
        kw in col_str
        for kw in [
            "amount", "transaction", "fraud", "price",
            "payment", "bank", "credit", "merchant", "card",
        ]
    ):
        recommended_cleaning = "quarantine"
        cleaning_rationale = (
            "Financial or Security data detected. 'Quarantine' is strictly recommended "
            "to isolate threats and anomalies without erasing the forensic evidence."
        )
    elif has_time and any(
        kw in col_str
        for kw in [
            "sensor", "temp", "reading", "humidity",
            "metric", "iot", "cpu", "memory", "speed",
        ]
    ):
        recommended_cleaning = "impute"
        cleaning_rationale = (
            "Sequential telemetry/sensor data detected. 'Predictive KNN Imputation' is "
            "recommended to smoothly bridge over hardware glitches or dropped signals."
        )
    elif any(
        kw in col_str
        for kw in [
            "age", "passenger", "survived", "income",
            "gender", "sex", "patient", "blood", "disease", "fare",
        ]
    ):
        recommended_cleaning = "impute"
        cleaning_rationale = (
            "Demographic data detected. 'Contextual Imputation' is recommended to salvage "
            "rows by predicting missing or anomalous user traits based on similar profiles."
        )
    elif is_large and len(numeric_cols) > 3:
        recommended_cleaning = "winsorize"
        cleaning_rationale = (
            "Large-scale numerical dataset detected. 'Winsorization' is recommended to "
            "smoothly cap extreme statistical outliers without shrinking your dataset size."
        )
    else:
        recommended_cleaning = "quarantine"
        cleaning_rationale = (
            "Generic dataset detected. 'Quarantine' is the safest default action. It moves "
            "anomalous rows to a secure vault while keeping your main dataset perfectly clean."
        )

    return {
        "status": "success",
        "session_id": session_id,
        "total_rows": len(df),
        "anomaly_count": sum(is_anomaly),
        "algorithm_used": algorithm,
        "recommendation": recommendation,
        "applied_rules": applied_rules,  # Neuro-Symbolic rules that fired
        "recommended_cleaning": recommended_cleaning,
        "cleaning_rationale": cleaning_rationale,
        "parquet_path": raw_parquet_path,
        "drift_report": drift_report,
    }