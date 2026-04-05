from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import shutil
import os
import duckdb  # <-- Added missing DuckDB import
import polars as pl
import pandas as pd
import numpy as np

# Ensure execute_natural_query handles the LLM translation in your core_engine!
from core_engine import process_and_detect, clean_dataset, get_viz_data, generate_insights, execute_natural_query, confirm_and_execute_edit

app = FastAPI(title="DataSentinel Local Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PYDANTIC MODELS ---
class CleanRequest(BaseModel):
    action: str = "drop"

class QueryEditRequest(BaseModel):
    user_query: str
    is_edit: bool = False

class ConfirmEditRequest(BaseModel):
    sql_query: str

# <-- THE FIX: Added the missing QueryRequest model
class QueryRequest(BaseModel):
    prompt: str


# --- ROUTES ---
@app.get("/")
def read_root():
    return {"message": "Antigravity bare-metal engine is online."}

@app.post("/api/upload")
async def upload_and_analyze(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported right now.")

    # --- THE NUKE PROTOCOL ---
    # Wipe the entire sessions directory to guarantee zero contamination
    if os.path.exists("./sessions"):
        shutil.rmtree("./sessions", ignore_errors=True)
    os.makedirs("./sessions", exist_ok=True)

    os.makedirs("./temp_uploads", exist_ok=True)
    temp_file_path = f"./temp_uploads/{file.filename}"

    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        results = process_and_detect(temp_file_path)
        if "error" in results:
            raise HTTPException(status_code=400, detail=results["error"])
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except PermissionError:
                pass

@app.get("/api/data/{session_id}")
def get_session_data(session_id: str, is_cleaned: str = "false", only_anomalies: str = "false"):
    file_name = "cleaned_data.parquet" if is_cleaned == "true" else "raw_data.parquet"
    parquet_path = f"./sessions/{session_id}/{file_name}"
    
    if not os.path.exists(parquet_path):
        raise HTTPException(status_code=404, detail=f"Session data not found at {parquet_path}")

    try:
        df = pl.read_parquet(parquet_path)
        
        if only_anomalies == "true" and "is_anomaly" in df.columns:
            anomaly_df = df.filter(pl.col("is_anomaly") == True)
            total_anomalies = len(anomaly_df)
            pandas_df = anomaly_df.head(100).to_pandas()
        else:
            total_anomalies = 0
            pandas_df = df.head(1000).to_pandas()
            
        # CRITICAL FIX: Industrial-grade NaN and Infinity sanitization for large datasets
        pandas_df = pandas_df.replace([np.inf, -np.inf], np.nan)
        pandas_df = pandas_df.astype(object).where(pd.notna(pandas_df), None)
        
        records = pandas_df.to_dict(orient="records")
        return {"data": records, "total_anomalies": total_anomalies}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse dataset chunk: {str(e)}")

@app.post("/api/clean/{session_id}")
def clean_data(session_id: str, request: CleanRequest):
    results = clean_dataset(session_id, request.action)
    if "error" in results: raise HTTPException(status_code=400, detail=results["error"])
    return results

@app.get("/api/download/{session_id}")
def download_cleaned_data(session_id: str):
    try:
        df = pl.read_parquet(f"./sessions/{session_id}/cleaned_data.parquet")
        csv_path = f"./sessions/{session_id}/cleaned_dataset.csv"
        df.write_csv(csv_path)
        return FileResponse(path=csv_path, filename="cleaned_dataset.csv", media_type="text/csv")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/viz/{session_id}")
def fetch_viz_data(session_id: str):
    try:
        results = get_viz_data(session_id)
        if "error" in results:
            raise HTTPException(status_code=400, detail=results["error"])
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/insights/{session_id}")
def fetch_insights(session_id: str):
    try:
        results = generate_insights(session_id)
        if "error" in results:
            raise HTTPException(status_code=400, detail=results["error"])
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/query/{session_id}")
async def query_data(session_id: str, request: QueryRequest):
    session_dir = f"./sessions/{session_id}"
    
    # 1. SMART FILE SELECTION
    processed_path = f"{session_dir}/processed_data.parquet"
    raw_path = f"{session_dir}/raw_data.parquet"
    
    if os.path.exists(processed_path):
        target_file = processed_path
    elif os.path.exists(raw_path):
        target_file = raw_path
    else:
        raise HTTPException(status_code=404, detail="No data found for this session. Please upload a file first.")

    try:
        # 2. Use your existing NLP to SQL engine from core_engine
        # Make sure execute_natural_query returns a dict like: {"results": [...], "sql": "SELECT ..."}
        results = execute_natural_query(session_id, request.prompt)
        
        if "error" in results:
            raise HTTPException(status_code=400, detail=results["error"])
            
        return results
        
    except Exception as e:
        error_msg = str(e)
        if "Threat_Score" in error_msg:
            error_msg = "Threat_Score not found. Did you forget to click 'Run Detection' first?"
        raise HTTPException(status_code=400, detail=error_msg)

@app.post("/api/query_edit/confirm/{session_id}")
def confirm_edit(session_id: str, request: ConfirmEditRequest):
    results = confirm_and_execute_edit(session_id, request.sql_query)
    if "error" in results: raise HTTPException(status_code=400, detail=results["error"])
    return results

@app.get("/api/quarantine/{session_id}")
def fetch_quarantine_vault(session_id: str):
    quarantine_path = f"./sessions/{session_id}/quarantined_data.parquet"
    
    if not os.path.exists(quarantine_path):
        return {"data": [], "count": 0}
        
    try:
        # Read the quarantined file
        df = pl.read_parquet(quarantine_path)
        
        # Convert to Pandas for safe JSON serialization, grab the top 100 for the UI
        pandas_df = df.head(100).to_pandas()
        pandas_df = pandas_df.replace([np.inf, -np.inf], np.nan)
        pandas_df = pandas_df.astype(object).where(pd.notna(pandas_df), None)
        
        return {
            "data": pandas_df.to_dict(orient="records"),
            "count": len(df)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))