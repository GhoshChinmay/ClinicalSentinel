import polars as pl
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.impute import KNNImputer
import numpy as np
import ollama
import duckdb
import re
import os
import uuid
import pandas as pd
import json
import requests

class SchemaEnforcer:
    @staticmethod
    def validate(df: pl.DataFrame) -> dict:
        errors = []
        if len(df) == 0:
            return {"valid": False, "errors": ["The uploaded dataset is completely empty."]}
            
        null_counts = df.null_count().to_dict(as_series=False)
        for col, count_list in null_counts.items():
            if count_list[0] == len(df):
                errors.append(f"Column '{col}' is 100% empty. Please remove ghost columns before uploading.")
                
        if len(df.columns) < 3:
            errors.append(f"Dataset only has {len(df.columns)} columns. A minimum of 3 columns is required for AI anomaly detection.")

        if errors:
            return {"valid": False, "errors": errors}
        
        return {"valid": True, "errors": []}

def process_text_anomalies(df: pl.DataFrame) -> pl.DataFrame:
    string_cols = [col for col, dtype in zip(df.columns, df.dtypes) if dtype in [pl.Utf8, getattr(pl, 'String', pl.Utf8)]]
    
    if not string_cols:
        return df
        
    print(f"DataSentinel: Auto-detected {len(string_cols)} text columns. Running Universal NLP Bridge...")
    
    new_features = []
    
    # --- PHASE A: STRUCTURAL SHAPE EXTRACTION ---
    for col in string_cols:
        df = df.with_columns(pl.col(col).fill_null(""))
        safe_len = pl.col(col).str.len_chars() + 0.0001
        
        new_features.extend([
            pl.col(col).str.len_chars().alias(f"{col}_length"),
            (pl.col(col).str.count_matches(r"\d") / safe_len).alias(f"{col}_digit_ratio"),
            (pl.col(col).str.count_matches(r"[A-Z]") / safe_len).alias(f"{col}_upper_ratio"),
            (pl.col(col).str.count_matches(r"[^\w\s]") / safe_len).alias(f"{col}_special_ratio")
        ])
        
    df = df.with_columns(new_features)

    # --- PHASE B: TF-IDF + PCA (THE NLP BRIDGE) ---
    if len(df) >= 100:
        df = df.with_columns(
            pl.concat_str([pl.col(c) for c in string_cols], separator=" ").alias("meta_text")
        )
        
        text_data = df["meta_text"].to_list()
        vectorizer = TfidfVectorizer(max_features=500, stop_words='english')
        
        try:
            tfidf_matrix = vectorizer.fit_transform(text_data)
            n_comps = min(3, tfidf_matrix.shape[1])
            if n_comps > 0:
                svd = TruncatedSVD(n_components=n_comps, random_state=42)
                pca_features = svd.fit_transform(tfidf_matrix)
                pca_cols = [pl.Series(f"nlp_pc{i+1}", pca_features[:, i]) for i in range(n_comps)]
                df = df.with_columns(pca_cols)
        except Exception as e:
            print(f"DataSentinel NLP Engine Warning: {e}")
        
        df = df.drop("meta_text")
        
    return df

def process_and_detect(file_path: str, session_id: str = None, algorithm: str = "isolation_forest"):
    if not session_id:
        session_id = str(uuid.uuid4())

    session_dir = f"./sessions/{session_id}"
    os.makedirs(session_dir, exist_ok=True)

    try:
        df = pl.read_csv(file_path, infer_schema_length=1000000)
    except Exception as e:
        try:
            pandas_fallback = pd.read_csv(file_path, low_memory=False)
            df = pl.from_pandas(pandas_fallback)
        except Exception as inner_e:
            return {"error": f"Fatal Read Error. Both engines failed to parse the CSV: {str(inner_e)}"}

    df = df.unique()

    # ---------------------------------------------------------
    # THE VELOCITY ENGINE (Time-Series Context)
    # ---------------------------------------------------------
    time_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower() or "timestamp" in c.lower()]
    entity_keywords = ["user", "account", "customer", "merchant", "employee", "sender", "client", "patient"]
    id_cols = [c for c in df.columns if "id" in c.lower() and any(kw in c.lower() for kw in entity_keywords)]

    velocity_cols_added = []  # Track which columns we create for later cleanup

    if time_cols and id_cols:
        t_col = time_cols[0]
        i_col = id_cols[0]
        
        print(f"DataSentinel: Time-Series detected. Tracking velocity for '{i_col}' over '{t_col}'...")
        
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
                        # Verify at least 50% of rows parsed successfully
                        null_pct = parsed[t_col].null_count() / len(parsed)
                        if null_pct < 0.5:
                            df = parsed
                            print(f"DataSentinel: Parsed '{t_col}' with format '{fmt}'.")
                            break
                        else:
                            parsed = None
                    except Exception:
                        continue
                
                if parsed is None:
                    raise ValueError(f"Could not parse '{t_col}' as datetime with any known format.")
            
            # Cast Date to Datetime if needed (rolling_sum_by requires Datetime)
            if df[t_col].dtype == pl.Date:
                df = df.with_columns(pl.col(t_col).cast(pl.Datetime))

            # Drop rows where datetime is null after parsing
            df = df.filter(pl.col(t_col).is_not_null())
            df = df.sort([i_col, t_col])
            
            # --- SMART COLUMN SELECTION ---
            # Prefer amount/value/price columns for velocity tracking
            numeric_cols_for_velocity = [c for c, d in zip(df.columns, df.dtypes) if d in [pl.Float64, pl.Int64, pl.Float32, pl.Int32]]
            amount_keywords = ["amount", "value", "price", "total", "balance", "sum", "cost", "payment"]
            smart_picks = [c for c in numeric_cols_for_velocity if any(kw in c.lower() for kw in amount_keywords)]
            track_col = smart_picks[0] if smart_picks else (numeric_cols_for_velocity[0] if numeric_cols_for_velocity else None)
            
            if track_col:
                df = df.with_columns(pl.lit(1).alias("_txn_counter"))
                df = df.with_columns([
                    pl.col(track_col).rolling_sum_by(by=t_col, window_size="1d", closed="both").over(i_col).alias("velocity_24h_sum"),
                    pl.col("_txn_counter").rolling_sum_by(by=t_col, window_size="1h", closed="both").over(i_col).alias("velocity_1h_count")
                ])
                # Fill nulls ONLY in the velocity columns, not the entire dataframe
                df = df.with_columns([
                    pl.col("velocity_24h_sum").fill_null(0),
                    pl.col("velocity_1h_count").fill_null(0),
                ])
                df = df.drop("_txn_counter")
                velocity_cols_added = ["velocity_24h_sum", "velocity_1h_count"]
                print(f"DataSentinel: Velocity tracking successfully generated for '{track_col}'.")
            else:
                print("DataSentinel: Velocity Engine skipped — no numeric columns found for tracking.")
        except Exception as e:
            print(f"DataSentinel: Velocity Engine skipped due to parsing error: {e}")

    df = process_text_anomalies(df)
    pandas_df = df.to_pandas()
    
    numeric_cols = [c for c in pandas_df.select_dtypes(include=[np.number]).columns.tolist() if c not in time_cols]
    cat_cols = pandas_df.select_dtypes(include=['object', 'string']).columns.tolist()

    encoded_df = pandas_df[numeric_cols].copy().fillna(0)
    for col in cat_cols:
        freq_encoding = pandas_df[col].value_counts(normalize=True)
        encoded_df[col + "_freq"] = pandas_df[col].map(freq_encoding).fillna(0)

    # ---------------------------------------------------------
    # THE AI DETECTION ENGINE (Z-Score Thresholding)
    # ---------------------------------------------------------
    recommendation = "Isolation Forest (Z-Score Scaled)"
    
    # We train the model but ignore its built-in, paranoid predictions
    model = IsolationForest(n_estimators=200, random_state=42)
    model.fit(encoded_df)

    # We extract the pure, raw mathematical 'weirdness' score for every row
    raw_scores = model.decision_function(encoded_df)
    inverted_scores = -raw_scores  # Higher = More anomalous
    
    # Calculate the exact average weirdness and the standard deviation
    mean_weirdness = np.mean(inverted_scores)
    std_weirdness = np.std(inverted_scores)
    
    # THE FIX: You are only flagged as an anomaly if you are 1.5 standard deviations above the average
    threshold = mean_weirdness + (1.5 * std_weirdness)
    is_anomaly = [True if s > threshold else False for s in inverted_scores]
    
    df = df.with_columns(pl.Series(name="is_anomaly", values=is_anomaly))

    # --- TIER 2 THREAT ENGINE (SUPERVISED OR SYNTHETIC) ---
    if "Class" in pandas_df.columns:
        try:
            X = encoded_df.drop(columns=["Class"]) if "Class" in encoded_df.columns else encoded_df
            y = pandas_df["Class"].fillna(0)
            
            classifier = HistGradientBoostingClassifier(class_weight="balanced", random_state=42)
            classifier.fit(X, y)
            
            probabilities = classifier.predict_proba(X)[:, 1] 
            threat_scores = [round(p * 100, 2) for p in probabilities]
            df = df.with_columns(pl.Series(name="Threat_Score", values=threat_scores))
        except Exception as e:
            print(f"Supervised Engine failed: {e}")
            df = df.with_columns(pl.Series(name="Threat_Score", values=[0] * len(pandas_df)))
    else:
        try:
            min_s = inverted_scores.min()
            max_s = inverted_scores.max()
            
            threat_scores = []
            if max_s > min_s:
                for i, s in enumerate(inverted_scores):
                    # Smart Scaling: Forces normal rows below 40%, and true anomalies above 60%
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
            print(f"Synthetic Engine failed: {e}")
            df = df.with_columns(pl.Series(name="Threat_Score", values=[0] * len(pandas_df)))

    # --- AI REASON GENERATOR ---
    # Exclude engineered columns from reason generation so explanations reference original data
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
            stats[col] = {
                "mean": pandas_df[col].mean(),
                "std": pandas_df[col].std()
            }
        
        # Velocity stats (if available)
        velocity_stats = {}
        for vc in velocity_cols_added:
            if vc in pandas_df.columns:
                velocity_stats[vc] = {
                    "mean": pandas_df[vc].mean(),
                    "std": pandas_df[vc].std()
                }
            
        rare_cats = {}
        for col in cat_cols:
            counts = pandas_df[col].value_counts(normalize=True)
            rare_cats[col] = counts[counts < 0.01].index.tolist()

        anomaly_indices = [i for i, x in enumerate(is_anomaly) if x]
        for idx in anomaly_indices:
            row = pandas_df.iloc[idx]
            reasons = []
            
            # Check velocity spikes first (most explainable for fraud-like anomalies)
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
    raw_parquet_path = f"{session_dir}/raw_data.parquet"
    df.write_parquet(raw_parquet_path)

    # ---------------------------------------------------------
    # --- SMART CLEANING RECOMMENDATION ENGINE (Upgraded) ---
    # ---------------------------------------------------------
    col_str = " ".join(df.columns).lower()
    
    # 1. Analyze the "Shape" of the dataset
    text_heavy = len(cat_cols) >= len(numeric_cols) and len(cat_cols) > 0
    is_large = len(pandas_df) > 2000
    has_time = len(time_cols) > 0

    # 2. NLP / Text-Heavy Data (e.g., Amazon Reviews)
    if text_heavy or any(kw in col_str for kw in ["review", "text", "description", "summary", "comment", "feedback"]):
        recommended_cleaning = "mask"
        cleaning_rationale = "Text-heavy dataset detected. We recommend 'Masking' to safely redact anomalous strings, typos, or bot-generated text with a [REDACTED] tag without destroying the rest of the row."
        
    # 3. Financial / Security Data (e.g., Credit Card Fraud)
    elif any(kw in col_str for kw in ["amount", "transaction", "fraud", "price", "payment", "bank", "credit", "merchant", "card"]):
        recommended_cleaning = "quarantine"
        cleaning_rationale = "Financial or Security data detected. 'Quarantine' is strictly recommended to isolate threats and anomalies without erasing the forensic evidence."

    # 4. IoT / Telemetry Data (e.g., Velocity Engine Test)
    elif has_time and any(kw in col_str for kw in ["sensor", "temp", "reading", "humidity", "metric", "iot", "cpu", "memory", "speed"]):
        recommended_cleaning = "impute"
        cleaning_rationale = "Sequential telemetry/sensor data detected. 'Predictive KNN Imputation' is recommended to smoothly bridge over hardware glitches or dropped signals."

    # 5. Demographic / Biological Data (e.g., Titanic)
    elif any(kw in col_str for kw in ["age", "passenger", "survived", "income", "gender", "sex", "patient", "blood", "disease", "fare"]):
        recommended_cleaning = "impute"
        cleaning_rationale = "Demographic data detected. 'Contextual Imputation' is recommended to salvage rows by predicting missing or anomalous user traits based on similar profiles."

    # 6. Massive Numerical Datasets
    elif is_large and len(numeric_cols) > 3:
        recommended_cleaning = "winsorize"
        cleaning_rationale = "Large-scale numerical dataset detected. 'Winsorization' is recommended to smoothly cap extreme statistical outliers without shrinking your dataset size."

    # 7. Safe Fallback
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
        "parquet_path": raw_parquet_path
    }

def clean_dataset(session_id: str, action: str = "drop"):
    session_dir = f"./sessions/{session_id}"
    raw_parquet_path = f"{session_dir}/raw_data.parquet"
    
    if not os.path.exists(raw_parquet_path): 
        return {"error": "Dataset not found."}
        
    df = pl.read_parquet(raw_parquet_path)
    original_count = len(df)
    
    if action in ["drop", "quarantine"]:
        quarantined_df = df.filter(pl.col("is_anomaly") == True)
        if len(quarantined_df) > 0:
            quarantined_df.write_parquet(f"{session_dir}/quarantined_data.parquet")
            
        cleaned_df = df.filter(pl.col("is_anomaly") == False)

    elif action == "winsorize":
        numeric_cols = [col for col, dtype in zip(df.columns, df.dtypes) if dtype in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]]
        normal_data = df.filter(pl.col("is_anomaly") == False)
        
        exprs = []
        for col in numeric_cols:
            if col in ["is_anomaly", "Threat_Score"]: continue 
            
            lower_bound = normal_data[col].quantile(0.05)
            upper_bound = normal_data[col].quantile(0.95)
            
            expr = pl.when(pl.col("is_anomaly") == True) \
                     .then(pl.col(col).clip(lower_bound, upper_bound)) \
                     .otherwise(pl.col(col)) \
                     .alias(col)
            exprs.append(expr)
            
        cleaned_df = df.with_columns(exprs)

    elif action == "mask":
        string_cols = [col for col, dtype in zip(df.columns, df.dtypes) if dtype in [pl.Utf8, getattr(pl, 'String', pl.Utf8)]]
        
        exprs = []
        for col in string_cols:
            if col in ["AI_Reason"]: continue
            
            expr = pl.when(pl.col("is_anomaly") == True) \
                     .then(pl.lit("[REDACTED_ANOMALY]")) \
                     .otherwise(pl.col(col)) \
                     .alias(col)
            exprs.append(expr)
            
        cleaned_df = df.with_columns(exprs)

    # ---------------------------------------------------------
    # ACTION 4: CONTEXTUAL IMPUTATION (Predictive KNN)
    # ---------------------------------------------------------
    elif action == "impute":
        numeric_cols = [col for col, dtype in zip(df.columns, df.dtypes) if dtype in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]]
        
        # We don't want to accidentally impute our own AI scoring columns or engineered frequency tags
        target_cols = [c for c in numeric_cols if c not in ["is_anomaly", "Threat_Score"] and not c.endswith("_freq")]
        
        if target_cols:
            print("DataSentinel: Running K-Nearest Neighbors Predictive Imputation...")
            
            # Scikit-Learn requires Pandas for this specific matrix transformation
            pandas_df = df.to_pandas()
            
            # Temporarily replace the anomalous values with 'NaN' (Not a Number)
            # This acts as a blank target for the Imputer to "fill in"
            for col in target_cols:
                pandas_df.loc[pandas_df["is_anomaly"] == True, col] = np.nan
                
            # Initialize KNN Imputer
            # n_neighbors=5: Looks at the 5 most mathematically similar rows to make its guess
            # weights="distance": Closer neighbors have a stronger vote in the final number
            imputer = KNNImputer(n_neighbors=5, weights="distance")
            
            # Run the prediction and overwrite the NaN values with the highly educated guesses
            pandas_df[target_cols] = imputer.fit_transform(pandas_df[target_cols])
            
            # Reconstruct the Polars DataFrame with the repaired columns
            for col in target_cols:
                df = df.with_columns(pl.Series(name=col, values=pandas_df[col]))
                
        cleaned_df = df

    else:
        return {"error": f"Unknown cleaning action: {action}"}

    # Strip ALL engineered columns: AI metadata, freq encodings, NLP features, velocity signals
    engineered_suffixes = ("_freq", "_length", "_digit_ratio", "_upper_ratio", "_special_ratio")
    engineered_prefixes = ("nlp_pc",)
    velocity_names = {"velocity_24h_sum", "velocity_1h_count"}
    always_drop = {"is_anomaly", "AI_Reason", "Threat_Score"}
    
    cols_to_drop = [
        c for c in cleaned_df.columns 
        if c in always_drop 
        or c.endswith(engineered_suffixes) 
        or any(c.startswith(p) for p in engineered_prefixes)
        or c in velocity_names
    ]
    cleaned_df = cleaned_df.drop([c for c in cols_to_drop if c in cleaned_df.columns])
        
    cleaned_parquet_path = f"{session_dir}/cleaned_data.parquet"
    cleaned_df.write_parquet(cleaned_parquet_path)
    
    return {
        "status": "success", 
        "action_taken": action,
        "original_rows": original_count,
        "new_total": len(cleaned_df)
    }

def get_global_histogram(df, numeric_cols):
    if df is None or len(df) == 0 or not numeric_cols: return []
    
    try:
        exprs = [
            ((pl.col(c) - pl.col(c).mean()) / (pl.col(c).std() + 1e-9)).alias(c)
            for c in numeric_cols
        ]
        normalized_df = df.select(exprs)
        
        flat_series = normalized_df.melt().drop_nulls().get_column("value")
        
        flat_values = flat_series.to_numpy()
        hist, bins = np.histogram(flat_values, bins=30, range=(-5, 5))
        
        return [{"bin": f"{bins[i]:.1f}σ", "count": int(hist[i])} for i in range(len(hist))]
    except Exception as e:
        print(f"Histogram Generation Failed: {e}")
        return []

def get_viz_data(session_id: str):
    session_dir = f"./sessions/{session_id}"
    raw_path = f"{session_dir}/raw_data.parquet"
    clean_path = f"{session_dir}/cleaned_data.parquet"
    
    if not os.path.exists(raw_path): 
        return {"error": "Data not found"}

    df_raw = pl.read_parquet(raw_path)
    df_clean = pl.read_parquet(clean_path) if os.path.exists(clean_path) else None
    
    internal_cols = ["is_anomaly", "Threat_Score", "Class"]
    
    numeric_cols = []
    categorical_cols = []
    
    # 1. Sort columns into Math vs. Text
    for c, d in zip(df_raw.columns, df_raw.dtypes):
        if c in internal_cols: continue
        if df_clean is not None and c not in df_clean.columns: continue
        
        if "Int" in str(d) or "Float" in str(d):
            numeric_cols.append(c)
        elif "String" in str(d) or "Utf8" in str(d) or "Object" in str(d):
            categorical_cols.append(c)

    # 2. Process Numeric Data (Same as before)
    correlation_data = None
    if len(numeric_cols) > 1:
        try:
            df_for_corr = df_clean if df_clean is not None else df_raw
            corr_df = df_for_corr.select(numeric_cols).to_pandas().corr().fillna(0)
            correlation_data = {"features": numeric_cols, "matrix": corr_df.values.tolist()}
        except: pass

    # 3. NEW: Process Text/Categorical Data (Top 10 Frequency)
    cat_data = []
    df_target = df_clean if df_clean is not None else df_raw
    for col in categorical_cols:
        try:
            # Count the occurrences of each text item and grab the top 10
            vc = df_target.get_column(col).value_counts().sort("count", descending=True).head(10)
            
            # Polars naming safety
            val_col = vc.columns[0]
            count_col = vc.columns[1]
            
            # Truncate super long text (like full reviews) to 35 chars for the UI
            items = [{"label": str(row[val_col])[:35] + ("..." if len(str(row[val_col])) > 35 else ""), "count": row[count_col]} for row in vc.to_dicts()]
            cat_data.append({"column": col, "top_values": items})
        except: pass

    return {
        "columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "global_raw_hist": get_global_histogram(df_raw, numeric_cols) if numeric_cols else [],
        "global_clean_hist": get_global_histogram(df_clean, numeric_cols) if df_clean is not None and numeric_cols else [],
        "clean_sample": df_clean.head(1000).to_dicts() if df_clean is not None else [],
        "correlation": correlation_data,
        "categorical_data": cat_data # Passing the text data to React!
    }

# --- KEY ALIASES: every known LLM variant for each OIA field ---
_OBSERVATION_KEYS = ['observation', 'observations', 'finding', 'findings', 'data_point', 'fact']
_INSIGHT_KEYS = ['insight', 'insights', 'analysis', 'impact', 'interpretation', 'implication']
_ACTION_KEYS = ['action', 'actions', 'recommendation', 'recommendations', 'recommended_action',
                'recommended_actions', 'suggested_action', 'next_step', 'next_steps',
                'remediation', 'resolution', 'suggestion', 'step']

def _fuzzy_get(obj: dict, aliases: list) -> str:
    """Search for a key in the dict using exact match, then partial/contains match."""
    # Exact match (case-insensitive)
    for alias in aliases:
        for k, v in obj.items():
            if k.lower() == alias and v is not None and str(v).strip():
                return str(v).strip()
    # Partial match (e.g. "recommended_action" contains "action")
    for alias in aliases:
        for k, v in obj.items():
            if alias in k.lower() and v is not None and str(v).strip():
                return str(v).strip()
    return ''

def _is_oia_like(keys: list) -> bool:
    lower = [k.lower() for k in keys]
    return (any(alias in l for l in lower for alias in _OBSERVATION_KEYS) or
            any(alias in l for l in lower for alias in _INSIGHT_KEYS) or
            any(alias in l for l in lower for alias in _ACTION_KEYS))

def _extract_oia_insights(raw_data) -> list:
    """
    Bulletproof recursive extractor that can dig OIA insight objects out of
    any arbitrarily nested structure the LLM might return.
    Uses fuzzy key matching and guarantees no field is ever empty.
    """
    if isinstance(raw_data, list):
        valid = []
        for item in raw_data:
            if isinstance(item, dict):
                if _is_oia_like(list(item.keys())):
                    obs = _fuzzy_get(item, _OBSERVATION_KEYS)
                    ins = _fuzzy_get(item, _INSIGHT_KEYS)
                    act = _fuzzy_get(item, _ACTION_KEYS)
                    if obs or ins:
                        valid.append({
                            "observation": obs or "Data pattern detected in the uploaded dataset.",
                            "insight": ins or "This pattern may impact downstream analysis and model training accuracy.",
                            "action": act or "Review the anomalies in the Detection tab and proceed to Cleaning for remediation.",
                        })
                    else:
                        for v in item.values():
                            valid.extend(_extract_oia_insights(v))
                else:
                    for v in item.values():
                        valid.extend(_extract_oia_insights(v))
            elif isinstance(item, list):
                valid.extend(_extract_oia_insights(item))
        return valid

    if isinstance(raw_data, dict):
        if _is_oia_like(list(raw_data.keys())):
            obs = _fuzzy_get(raw_data, _OBSERVATION_KEYS)
            ins = _fuzzy_get(raw_data, _INSIGHT_KEYS)
            act = _fuzzy_get(raw_data, _ACTION_KEYS)
            if obs or ins:
                return [{
                    "observation": obs or "Data pattern detected in the uploaded dataset.",
                    "insight": ins or "This pattern may impact downstream analysis and model training accuracy.",
                    "action": act or "Review the anomalies in the Detection tab and proceed to Cleaning for remediation.",
                }]

        results = []
        for v in raw_data.values():
            results.extend(_extract_oia_insights(v))
        return results

    return []


def _build_rich_context(df_raw: pl.DataFrame) -> str:
    """Build a richer dataset summary to give the LLM more signal."""
    total_rows = len(df_raw)
    columns = df_raw.columns
    anomaly_count = 0
    if "is_anomaly" in df_raw.columns:
        anomaly_count = df_raw.filter(pl.col("is_anomaly") == True).height
    anomaly_pct = round((anomaly_count / total_rows) * 100, 2) if total_rows > 0 else 0

    numeric_cols = [c for c, d in zip(df_raw.columns, df_raw.dtypes) if d in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]]
    text_cols = [c for c, d in zip(df_raw.columns, df_raw.dtypes) if d in [pl.Utf8, getattr(pl, 'String', pl.Utf8)]]

    # Quick stats for top numeric columns
    stat_lines = []
    for c in numeric_cols[:5]:
        try:
            series = df_raw[c].drop_nulls()
            if len(series) > 0:
                stat_lines.append(f"  - {c}: min={series.min()}, max={series.max()}, mean={series.mean():.2f}, nulls={df_raw[c].null_count()}")
        except:
            pass

    stats_block = "\n".join(stat_lines) if stat_lines else "  (no numeric stats available)"

    return f"""Dataset Context:
- Total Rows: {total_rows}
- Total Columns: {len(columns)}
- Detected Anomalies: {anomaly_count} ({anomaly_pct}%)
- Numeric Columns ({len(numeric_cols)}): {', '.join(numeric_cols[:10])}
- Text Columns ({len(text_cols)}): {', '.join(text_cols[:10])}
- Key Statistics:
{stats_block}
- All Column Names: {', '.join(columns)}"""


def generate_insights(session_id: str):
    session_dir = f"./sessions/{session_id}"
    raw_path = f"{session_dir}/raw_data.parquet"
    
    if not os.path.exists(raw_path): 
        return {"error": "Data not found"}

    df_raw = pl.read_parquet(raw_path)
    total_rows = len(df_raw)
    columns = df_raw.columns
    anomaly_count = 0
    if "is_anomaly" in df_raw.columns:
        anomaly_count = df_raw.filter(pl.col("is_anomaly") == True).height

    context_block = _build_rich_context(df_raw)

    prompt = f"""You are an elite Data Science Consultant. Analyze this dataset and provide exactly 3 critical insights.

{context_block}

RESPOND WITH ONLY A RAW JSON ARRAY. No markdown, no explanation, no wrapper object.
Use this exact schema:
[
  {{"observation": "...", "insight": "...", "action": "..."}},
  {{"observation": "...", "insight": "...", "action": "..."}},
  {{"observation": "...", "insight": "...", "action": "..."}}
]"""

    def _build_fallback():
        """Guaranteed static OIA insights based on the actual data profile."""
        return [
            {
                "observation": f"The anomaly detection engine flagged {anomaly_count} out of {total_rows} rows ({round(anomaly_count / max(total_rows, 1) * 100, 1)}%) as statistically anomalous.",
                "insight": "These outliers will disproportionately skew aggregate statistics (mean, variance) and degrade the performance of downstream ML models if left untreated.",
                "action": "Navigate to the Cleaning tab and select 'Quarantine' to safely isolate these rows into a forensic vault without permanently deleting them."
            },
            {
                "observation": f"The dataset contains {len(columns)} distinct features spanning numeric, categorical, and potentially temporal dimensions.",
                "insight": "High dimensionality increases the risk of the 'curse of dimensionality' — models struggle to find signal in noisy, wide datasets. Correlated features also inflate model complexity.",
                "action": "Use the Visualizer tab to inspect the correlation heatmap and identify redundant or highly correlated features that can be safely dropped before modeling."
            },
            {
                "observation": f"Data profiling across all {total_rows} rows completed successfully. The schema includes columns: {', '.join(columns[:6])}{'...' if len(columns) > 6 else ''}.",
                "insight": "Proper schema validation and anomaly isolation before modeling ensures that your training pipeline receives clean, statistically sound inputs — directly improving accuracy and reducing false positives.",
                "action": "After cleaning, export the sanitized CSV from the Edit tab to ensure all engineered features are stripped and only original columns remain in the final output."
            }
        ]

    try:
        response = requests.post("http://localhost:11434/api/generate", json={
            "model": "phi3",
            "prompt": prompt,
            "format": "json",
            "stream": False
        }, timeout=120)
        
        if response.status_code == 200:
            response_text = response.json().get("response", "").strip()
            print(f"DataSentinel Insights Raw LLM Response: {response_text[:500]}")
            
            # Strip markdown fences
            if "```" in response_text:
                response_text = re.sub(r'```(?:json)?\s*', '', response_text)
                response_text = response_text.strip()
            
            # Parse JSON
            parsed = json.loads(response_text)
            
            # Extract OIA objects from whatever structure the model returned
            insights_list = _extract_oia_insights(parsed)
            
            if insights_list and len(insights_list) > 0:
                print(f"DataSentinel: Successfully extracted {len(insights_list)} OIA insights.")
                return {"insights": insights_list}
            else:
                print("DataSentinel: LLM returned valid JSON but no OIA objects found. Using fallback.")
                return {"insights": _build_fallback()}
        else:
            raise Exception(f"Local LLM returned status {response.status_code}")
            
    except json.JSONDecodeError as je:
        print(f"DataSentinel Insights JSON Parse Error: {je}")
        return {"insights": _build_fallback()}
    except requests.exceptions.ConnectionError:
        print("DataSentinel: Ollama is not running. Using intelligent fallback.")
        return {"insights": _build_fallback()}
    except requests.exceptions.Timeout:
        print("DataSentinel: LLM request timed out. Using fallback.")
        return {"insights": _build_fallback()}
    except Exception as e:
        print(f"DataSentinel Insights Error: {e}")
        return {"insights": _build_fallback()}

def execute_natural_query(session_id: str, user_query: str, is_edit: bool = False):
    session_dir = f"./sessions/{session_id}"
    data_path = f"{session_dir}/cleaned_data.parquet" if os.path.exists(f"{session_dir}/cleaned_data.parquet") else f"{session_dir}/raw_data.parquet"
    
    if not os.path.exists(data_path):
        return {"error": "Dataset not found."}

    try:
        df = pl.read_parquet(data_path)
        schema_str = ", ".join([f"{col} ({str(dtype)})" for col, dtype in zip(df.columns, df.dtypes)])

        system_prompt = f"""
        You are an expert SQL Data Analyst. The dataset schema is: {schema_str}
        Table name MUST be exactly: 'my_table'
        User request: "{user_query}"
        """
        
        if is_edit:
            system_prompt += "\nReturn ONLY a valid SQL UPDATE or DELETE statement. You are a machine. Do NOT output conversational text like 'Here is the query'. Start your response strictly with the word UPDATE or DELETE."
        else:
            system_prompt += "\nReturn ONLY a valid SQL SELECT statement. You are a machine. Do NOT output conversational text. Start your response strictly with the word SELECT."

        # THE HYBRID ROUTER FIX:
        # We explicitly ping llama3:latest here to handle the heavy SQL reasoning.
        response = ollama.chat(model='llama3:latest', messages=[{'role': 'system', 'content': system_prompt}])
        raw_response = response['message']['content'].strip()

        match = re.search(r'```sql\n(.*?)```', raw_response, re.DOTALL)
        if match:
            sql_query = match.group(1).strip()
        else:
            sql_query = re.sub(r'^```sql\n|```$', '', raw_response, flags=re.MULTILINE).strip()
            sql_query = re.sub(r'^```\n|```$', '', sql_query, flags=re.MULTILINE).strip()
            sql_query = re.sub(r'^SELECT\s+', 'SELECT ', sql_query, flags=re.IGNORECASE)
            sql_query = re.sub(r'^UPDATE\s+', 'UPDATE ', sql_query, flags=re.IGNORECASE)
            sql_query = re.sub(r'^DELETE\s+', 'DELETE ', sql_query, flags=re.IGNORECASE)

        if is_edit:
            return {"sql": sql_query}
        else:
            try:
                con = duckdb.connect()
                # Safely mapping the Parquet file to the 'my_table' view directly in DuckDB
                con.execute(f"CREATE VIEW my_table AS SELECT * FROM '{data_path}'")
                result_df = con.query(sql_query).pl()
                return {"sql": sql_query, "columns": result_df.columns, "data": result_df.head(100).to_dicts()}
            except Exception as e:
                return {"error": f"Failed to execute. SQL: {sql_query} | Error: {str(e)}"}
    except Exception as e:
        return {"error": f"Failed to generate SQL: {str(e)}"}

def confirm_and_execute_edit(session_id: str, sql_query: str):
    session_dir = f"./sessions/{session_id}"
    data_path = f"{session_dir}/cleaned_data.parquet" if os.path.exists(f"{session_dir}/cleaned_data.parquet") else f"{session_dir}/raw_data.parquet"
    
    try:
        con = duckdb.connect()
        con.execute(f"CREATE TABLE my_table AS SELECT * FROM '{data_path}'")
        
        clean_sql = sql_query.strip().rstrip(';')
        if not clean_sql.upper().endswith("RETURNING *"):
            clean_sql += " RETURNING *"
            
        affected_df = con.query(clean_sql).pl()
        con.execute(f"COPY my_table TO '{data_path}' (FORMAT PARQUET)")
        
        return {
            "status": "success",
            "rows_affected": len(affected_df),
            "columns": affected_df.columns,
            "preview_data": affected_df.head(50).to_dicts()
        }
    except Exception as e:
        return {"error": str(e)}