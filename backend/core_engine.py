import polars as pl
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
import numpy as np
import ollama
import duckdb
import re
import os
import uuid
import pandas as pd

def process_text_anomalies(df: pl.DataFrame) -> pl.DataFrame:
    """
    Universally extracts structural math and NLP context from any text columns.
    """
    # Identify all string columns dynamically (handles both older and newer Polars string types)
    string_cols = [col for col, dtype in zip(df.columns, df.dtypes) if dtype in [pl.Utf8, getattr(pl, 'String', pl.Utf8)]]
    
    if not string_cols:
        return df # No text columns found, skip!
        
    print(f"DataSentinel: Auto-detected {len(string_cols)} text columns. Running Universal NLP Bridge...")
    
    new_features = []
    
    # --- PHASE A: STRUCTURAL SHAPE EXTRACTION ---
    for col in string_cols:
        # Fill nulls with empty strings to prevent math crashes
        df = df.with_columns(pl.col(col).fill_null(""))
        
        # Safe length (add 0.0001 to avoid dividing by zero)
        safe_len = pl.col(col).str.len_chars() + 0.0001
        
        new_features.extend([
            pl.col(col).str.len_chars().alias(f"{col}_length"),
            (pl.col(col).str.count_matches(r"\d") / safe_len).alias(f"{col}_digit_ratio"),
            (pl.col(col).str.count_matches(r"[A-Z]") / safe_len).alias(f"{col}_upper_ratio"),
            (pl.col(col).str.count_matches(r"[^\w\s]") / safe_len).alias(f"{col}_special_ratio")
        ])
        
    df = df.with_columns(new_features)

    # --- PHASE B: TF-IDF + PCA (THE NLP BRIDGE) ---
    # Combine all text columns into one massive "meta-document" per row
    df = df.with_columns(
        pl.concat_str([pl.col(c) for c in string_cols], separator=" ").alias("meta_text")
    )
    
    text_data = df["meta_text"].to_list()
    
    # Vectorize the text (limit to top 500 words to save memory)
    vectorizer = TfidfVectorizer(max_features=500, stop_words='english')
    try:
        tfidf_matrix = vectorizer.fit_transform(text_data)
        
        # Compress down to max 3 numerical signals
        n_comps = min(3, tfidf_matrix.shape[1])
        if n_comps > 0:
            svd = TruncatedSVD(n_components=n_comps, random_state=42)
            pca_features = svd.fit_transform(tfidf_matrix)
            
            pca_cols = [pl.Series(f"nlp_pc{i+1}", pca_features[:, i]) for i in range(n_comps)]
            df = df.with_columns(pca_cols)
    except Exception as e:
        print(f"DataSentinel NLP Engine Warning: {e}")
    
    # Drop the temporary meta column, but KEEP original text columns for the UI
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

    # --- NEW: DEDUPLICATION ---
    df = df.unique()

    # --- NEW: UNIVERSAL TEXT ENGINE ---
    df = process_text_anomalies(df)

    pandas_df = df.to_pandas()
    numeric_cols = pandas_df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = pandas_df.select_dtypes(include=['object', 'string']).columns.tolist()

    encoded_df = pandas_df[numeric_cols].copy().fillna(0)
    for col in cat_cols:
        freq_encoding = pandas_df[col].value_counts(normalize=True)
        encoded_df[col + "_freq"] = pandas_df[col].map(freq_encoding).fillna(0)

    recommendation = "Isolation Forest" if len(df) > 1000 else "Local Outlier Factor"
    
    if algorithm == "isolation_forest":
        model = IsolationForest(contamination=0.05, random_state=42)
        predictions = model.fit_predict(encoded_df)
    else:
        model = LocalOutlierFactor(n_neighbors=20, contamination=0.05, novelty=True)
        model.fit(encoded_df)
        predictions = model.predict(encoded_df)

    is_anomaly = [True if x == -1 else False for x in predictions]
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
        # --- NEW: SYNTHETIC THREAT SCORE FOR UNLABELED DATASETS ---
        try:
            if algorithm == "isolation_forest":
                raw_scores = model.decision_function(encoded_df)
            else:
                raw_scores = model.negative_outlier_factor_
                
            # Invert scores (so more anomalous = higher number)
            inverted_scores = -raw_scores
            min_s = inverted_scores.min()
            max_s = inverted_scores.max()
            
            # Scale the scores from 0 to 100% based on their mathematical severity
            if max_s > min_s:
                threat_scores = [round(((s - min_s) / (max_s - min_s)) * 100, 2) for s in inverted_scores]
            else:
                threat_scores = [0] * len(pandas_df)
                
            df = df.with_columns(pl.Series(name="Threat_Score", values=threat_scores))
        except Exception as e:
            print(f"Synthetic Engine failed: {e}")
            df = df.with_columns(pl.Series(name="Threat_Score", values=[0] * len(pandas_df)))

    # --- AI REASON GENERATOR ---
    reasons_list = [""] * len(pandas_df)
    
    if any(is_anomaly):
        stats = {}
        for col in numeric_cols:
            stats[col] = {
                "mean": pandas_df[col].mean(),
                "std": pandas_df[col].std()
            }
            
        rare_cats = {}
        for col in cat_cols:
            counts = pandas_df[col].value_counts(normalize=True)
            rare_cats[col] = counts[counts < 0.01].index.tolist()

        anomaly_indices = [i for i, x in enumerate(is_anomaly) if x]
        for idx in anomaly_indices:
            row = pandas_df.iloc[idx]
            reasons = []
            
            for col in numeric_cols:
                col_mean = stats[col]["mean"]
                col_std = stats[col]["std"]
                
                if row[col] > col_mean + (3 * col_std):
                    reasons.append(f"'{col}' ({row[col]:.1f}) is exceptionally high compared to the average ({col_mean:.1f}).")
                elif row[col] < col_mean - (3 * col_std):
                    reasons.append(f"'{col}' ({row[col]:.1f}) is suspiciously low compared to normal patterns.")
            
            for col in cat_cols:
                val = str(row[col])
                if val in rare_cats[col]:
                    reasons.append(f"The text '{val}' in '{col}' is extremely rare (possible typo).")
            
            if not reasons:
                reasons.append("Complex anomaly: The combination of these variables breaks standard dataset patterns.")
                
            reasons_list[idx] = " | ".join(reasons[:2])

    df = df.with_columns(pl.Series(name="AI_Reason", values=reasons_list))
    raw_parquet_path = f"{session_dir}/raw_data.parquet"
    df.write_parquet(raw_parquet_path)

    return {
        "status": "success",
        "session_id": session_id,
        "total_rows": len(df),
        "anomaly_count": sum(is_anomaly),
        "recommendation": recommendation,
        "parquet_path": raw_parquet_path
    }

def clean_dataset(session_id: str, action: str = "drop"):
    session_dir = f"./sessions/{session_id}"
    raw_parquet_path = f"{session_dir}/raw_data.parquet"
    
    if not os.path.exists(raw_parquet_path): 
        return {"error": "Dataset not found."}
        
    df = pl.read_parquet(raw_parquet_path)
    original_count = len(df)
    
    # ---------------------------------------------------------
    # ACTION 1: THE QUARANTINE (Soft Deletion)
    # ---------------------------------------------------------
    if action in ["drop", "quarantine"]:
        quarantined_df = df.filter(pl.col("is_anomaly") == True)
        if len(quarantined_df) > 0:
            quarantined_df.write_parquet(f"{session_dir}/quarantined_data.parquet")
            
        cleaned_df = df.filter(pl.col("is_anomaly") == False)

    # ---------------------------------------------------------
    # ACTION 2: SMART WINSORIZATION (Capping)
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # ACTION 3: CATEGORICAL MASKING (The Redaction)
    # ---------------------------------------------------------
    elif action == "mask":
        string_cols = [col for col, dtype in zip(df.columns, df.dtypes) if dtype in [pl.Utf8, getattr(pl, 'String', pl.Utf8)]]
        
        exprs = []
        for col in string_cols:
            if col in ["AI_Reason"]: continue
            
            # If it's an anomaly, overwrite the text with a safe placeholder
            expr = pl.when(pl.col("is_anomaly") == True) \
                     .then(pl.lit("[REDACTED_ANOMALY]")) \
                     .otherwise(pl.col(col)) \
                     .alias(col)
            exprs.append(expr)
            
        cleaned_df = df.with_columns(exprs)

    # ---------------------------------------------------------
    # ACTION 4: CONTEXTUAL IMPUTATION (Smart Replacement)
    # ---------------------------------------------------------
    elif action == "impute":
        numeric_cols = [col for col, dtype in zip(df.columns, df.dtypes) if dtype in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]]
        normal_data = df.filter(pl.col("is_anomaly") == False)
        
        exprs = []
        for col in numeric_cols:
            if col in ["is_anomaly", "Threat_Score"]: continue 
            
            # Find the true median of the healthy data to act as the baseline
            healthy_baseline = normal_data[col].median()
            
            # Replace the anomaly with the healthy baseline
            expr = pl.when(pl.col("is_anomaly") == True) \
                     .then(pl.lit(healthy_baseline)) \
                     .otherwise(pl.col(col)) \
                     .alias(col)
            exprs.append(expr)
            
        cleaned_df = df.with_columns(exprs)

    else:
        return {"error": f"Unknown cleaning action: {action}"}

    # ---------------------------------------------------------
    # FINAL CLEANUP & EXPORT
    # ---------------------------------------------------------
    cols_to_drop = ["is_anomaly", "AI_Reason", "Threat_Score"] + [c for c in df.columns if c.endswith("_freq")]
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
    numeric_cols = [
        c for c, d in zip(df_raw.columns, df_raw.dtypes) 
        if ("Int" in str(d) or "Float" in str(d)) and c not in internal_cols
    ]

    return {
        "columns": numeric_cols,
        "global_raw_hist": get_global_histogram(df_raw, numeric_cols),
        "global_clean_hist": get_global_histogram(df_clean, numeric_cols) if df_clean is not None else [],
        "clean_sample": df_clean.head(1000).to_dicts() if df_clean is not None else []
    }

def generate_insights(session_id: str):
    session_dir = f"./sessions/{session_id}"
    data_path = f"{session_dir}/cleaned_data.parquet" if os.path.exists(f"{session_dir}/cleaned_data.parquet") else f"{session_dir}/raw_data.parquet"
    
    if not os.path.exists(data_path):
        return {"error": "Dataset not found for insights."}

    try:
        df = pl.read_parquet(data_path)
        summary = f"Dataset Summary:\nRows: {len(df)}\nColumns: {', '.join(df.columns)}"
        
        response = ollama.chat(model='llama3:latest', messages=[
            {'role': 'system', 'content': "You are a professional Data Scientist. Provide a 3-sentence high-level summary of this dataset's structure and potential."},
            {'role': 'user', 'content': summary}
        ])
        return {"insights": response['message']['content']}
    
    except Exception as e:
        print(f"Ollama Crash: {str(e)}")
        return {"error": f"AI Engine Error: {str(e)}"}

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

        # FIX: Updated to 'llama3:latest' to match your local setup
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