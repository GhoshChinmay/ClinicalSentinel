import polars as pl
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.ensemble import HistGradientBoostingClassifier
import numpy as np
import ollama
import duckdb
import re
import os
import uuid
import pandas as pd

def process_and_detect(file_path: str, session_id: str = None, algorithm: str = "isolation_forest"):
    if not session_id:
        session_id = str(uuid.uuid4())

    session_dir = f"./sessions/{session_id}"
    os.makedirs(session_dir, exist_ok=True)

    try:
        # Attempt 1: Ultra-fast Polars strict read (scans a massive 1 million rows to be safe)
        df = pl.read_csv(file_path, infer_schema_length=1000000)
    except Exception as e:
        try:
            # Attempt 2: The Bulletproof Pandas Fallback
            # If Polars chokes on scientific notation, Pandas will force it through
            pandas_fallback = pd.read_csv(file_path, low_memory=False)
            df = pl.from_pandas(pandas_fallback)
        except Exception as inner_e:
            return {"error": f"Fatal Read Error. Both engines failed to parse the CSV: {str(inner_e)}"}

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

    # --- NEW: TIER 2 SUPERVISED THREAT ENGINE (PRECISION/RECALL) ---
    if "Class" in pandas_df.columns:
        try:
            # Safely use the encoded_df so the ML model doesn't crash on text columns
            X = encoded_df.drop(columns=["Class"]) if "Class" in encoded_df.columns else encoded_df
            y = pandas_df["Class"].fillna(0)
            
            # High-speed Gradient Booster balancing the extreme fraud ratio
            classifier = HistGradientBoostingClassifier(class_weight="balanced", random_state=42)
            classifier.fit(X, y)
            
            # Extract 0-100% Threat Score
            probabilities = classifier.predict_proba(X)[:, 1] 
            threat_scores = [round(p * 100, 2) for p in probabilities]
            df = df.with_columns(pl.Series(name="Threat_Score", values=threat_scores))
        except Exception as e:
            print(f"Supervised Engine failed: {e}")
            df = df.with_columns(pl.Series(name="Threat_Score", values=[0] * len(pandas_df)))
    else:
        # Fallback if it's not the Kaggle Dataset / no target column exists
        df = df.with_columns(pl.Series(name="Threat_Score", values=[0] * len(pandas_df)))

    # --- THE MASSIVE PERFORMANCE UPGRADE ---
    reasons_list = [""] * len(pandas_df)
    
    if any(is_anomaly):
        # 1. PRE-CALCULATE stats ONCE for the whole dataset
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

        # 2. Assign reasons instantly
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
    if not os.path.exists(raw_parquet_path): return {"error": "Dataset not found."}
        
    df = pl.read_parquet(raw_parquet_path)
    original_count = len(df)
    
    if action == "drop":
        cleaned_df = df.filter(pl.col("is_anomaly") == False)
    elif action == "cap":
        numeric_cols = [col for col, dtype in zip(df.columns, df.dtypes) if dtype in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]]
        pandas_df = df.to_pandas()
        for col in numeric_cols:
            lower = pandas_df[col].quantile(0.05)
            upper = pandas_df[col].quantile(0.95)
            pandas_df.loc[pandas_df['is_anomaly'], col] = pandas_df.loc[pandas_df['is_anomaly'], col].clip(lower, upper)
        cleaned_df = pl.from_pandas(pandas_df)

    # Clean up markers
    cols_to_drop = ["is_anomaly", "AI_Reason", "Threat_Score"] + [c for c in cleaned_df.columns if c.endswith("_freq")]
    cleaned_df = cleaned_df.drop([c for c in cols_to_drop if c in cleaned_df.columns])
        
    cleaned_parquet_path = f"{session_dir}/cleaned_data.parquet"
    cleaned_df.write_parquet(cleaned_parquet_path)
    
    return {"status": "success", "new_total": len(cleaned_df)}

# --- REPLACEMENT FOR core_engine.py ---

def get_global_histogram(df, numeric_cols):
    if df is None or len(df) == 0 or not numeric_cols: return []
    
    try:
        # 1. Stay natively inside Polars (avoids the Pandas NA crash entirely)
        exprs = [
            ((pl.col(c) - pl.col(c).mean()) / (pl.col(c).std() + 1e-9)).alias(c)
            for c in numeric_cols
        ]
        normalized_df = df.select(exprs)
        
        # 2. Melt into a single column and drop nulls safely
        flat_series = normalized_df.melt().drop_nulls().get_column("value")
        
        # 3. Convert to a pure numpy array for the final histogram
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
    
    # THE FIX: Get numeric columns but EXCLUDE the internal AI columns
    # This prevents the histogram from looking for columns we deleted during cleaning
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
    df = pl.read_parquet(data_path)
    summary = f"Rows: {len(df)}\nCols: {len(df.columns)}\nSchema: " + ", ".join(df.columns)
    
    try:
        response = ollama.chat(model='llama3', messages=[
            {'role': 'system', 'content': "You are a Data Scientist. Write a short, plain-English summary of this dataset."},
            {'role': 'user', 'content': summary}
        ])
        return {"insights": response['message']['content']}
    except Exception:
        return {"error": "Local AI Server (Ollama) is not running."}

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

        response = ollama.chat(model='llama3', messages=[{'role': 'system', 'content': system_prompt}])
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