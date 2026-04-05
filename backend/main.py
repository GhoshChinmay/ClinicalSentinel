"""
DataSentinel — FastAPI Application
API routes, file upload handling, and session management.
"""

import os
import polars as pl
from fastapi import FastAPI, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from utils import _session_dir, _BACKEND_DIR, logger, validate_session_id, cleanup_stale_sessions
from schema import SchemaEnforcer
from engines import (
    process_and_detect,
    clean_dataset,
    get_viz_data,
    generate_insights,
    execute_natural_query,
    confirm_and_execute_edit,
)

app = FastAPI()

# --- CORS: environment-based whitelist instead of wildcard ---
_ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "DataSentinel detection engine is online."}


@app.post("/api/upload/")
async def upload_csv(file: UploadFile = File(...)):
    # Clean up stale sessions (>24h old) instead of nuking everything
    cleanup_stale_sessions(max_age_hours=24)

    os.makedirs(os.path.join(_BACKEND_DIR, "temp_uploads"), exist_ok=True)
    temp_file_path = os.path.join(_BACKEND_DIR, "temp_uploads", file.filename)

    try:
        contents = await file.read()
        with open(temp_file_path, "wb") as f:
            f.write(contents)

        # --- SCHEMA VALIDATION ---
        try:
            df = pl.read_csv(temp_file_path, infer_schema_length=1000000)
        except Exception:
            import pandas as pd
            df = pl.from_pandas(pd.read_csv(temp_file_path, low_memory=False))

        validation = SchemaEnforcer.validate(df)
        if not validation["valid"]:
            return JSONResponse(
                status_code=400,
                content={"status": "rejected", "errors": validation["errors"]},
            )

        # Pass the already-loaded DataFrame to avoid double read
        result = process_and_detect(df=df, file_path=temp_file_path)
        return result

    except Exception as e:
        logger.error("Upload failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@app.get("/api/data/{session_id}")
def get_data(
    session_id: str,
    is_cleaned: bool = Query(False),
    only_anomalies: bool = Query(False),
):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    session_dir = _session_dir(session_id)

    if is_cleaned:
        parquet_path = f"{session_dir}/cleaned_data.parquet"
    else:
        parquet_path = f"{session_dir}/raw_data.parquet"

    if not os.path.exists(parquet_path):
        return JSONResponse(status_code=404, content={"error": "Data not found"})

    df = pl.read_parquet(parquet_path)

    total_anomalies = 0
    if "is_anomaly" in df.columns:
        anomalies = df.filter(pl.col("is_anomaly") == True)
        total_anomalies = len(anomalies)
        if only_anomalies:
            df = anomalies

    return {
        "data": df.to_dicts(),
        "total_anomalies": total_anomalies,
    }


@app.post("/api/clean/{session_id}")
def clean_data(session_id: str, action: str = Query("drop")):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    result = clean_dataset(session_id, action)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/api/compare/{session_id}")
def compare_data(session_id: str):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    session_dir = _session_dir(session_id)
    raw_path = f"{session_dir}/raw_data.parquet"
    clean_path = f"{session_dir}/cleaned_data.parquet"

    if not os.path.exists(clean_path):
        return JSONResponse(status_code=400, content={"error": "No cleaned data found."})

    df_raw = pl.read_parquet(raw_path)
    df_clean = pl.read_parquet(clean_path)

    is_dropped = len(df_clean) < len(df_raw)

    internal_cols = {"is_anomaly", "Threat_Score", "AI_Reason"}
    engineered_suffixes = ("_freq", "_length", "_digit_ratio", "_upper_ratio", "_special_ratio")
    engineered_prefixes = ("nlp_pc",)
    velocity_names = {"velocity_24h_sum", "velocity_1h_count"}

    cols_to_drop = [
        c for c in df_raw.columns
        if c in internal_cols
        or c.endswith(engineered_suffixes)
        or any(c.startswith(p) for p in engineered_prefixes)
        or c in velocity_names
    ]
    df_raw_clean_view = df_raw.drop([c for c in cols_to_drop if c in df_raw.columns])

    return {
        "is_dropped": is_dropped,
        "original": df_raw_clean_view.head(50).to_dicts(),
        "cleaned": df_clean.head(50).to_dicts(),
        "count": len(df_clean),
    }


@app.get("/api/viz/{session_id}")
def viz_data(session_id: str):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    result = get_viz_data(session_id)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/api/insights/{session_id}")
def insights(session_id: str):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    result = generate_insights(session_id)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/api/download/{session_id}")
def download_data(session_id: str, source: str = Query("cleaned")):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    session_dir = _session_dir(session_id)

    if source == "quarantine":
        parquet_path = f"{session_dir}/quarantined_data.parquet"
        csv_filename = "quarantined_data.csv"
    else:
        parquet_path = f"{session_dir}/cleaned_data.parquet"
        csv_filename = "cleaned_data.csv"

    if not os.path.exists(parquet_path):
        return JSONResponse(status_code=404, content={"error": f"No {source} data found."})

    df = pl.read_parquet(parquet_path)

    # Strip internal columns if present
    internal_cols = {"is_anomaly", "Threat_Score", "AI_Reason"}
    cols_to_drop = [c for c in df.columns if c in internal_cols]
    if cols_to_drop:
        df = df.drop(cols_to_drop)

    csv_path = f"{session_dir}/{csv_filename}"
    df.write_csv(csv_path)

    return FileResponse(path=csv_path, media_type="text/csv", filename=csv_filename)


@app.get("/api/quarantine/{session_id}")
def get_quarantine(session_id: str):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    session_dir = _session_dir(session_id)
    quarantine_path = f"{session_dir}/quarantined_data.parquet"

    if not os.path.exists(quarantine_path):
        return {"data": [], "count": 0}

    df = pl.read_parquet(quarantine_path)
    return {"data": df.to_dicts(), "count": len(df)}


@app.post("/api/query/{session_id}")
def query_data(session_id: str, user_query: str = Query(...), mode: str = Query("explore")):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    is_edit = mode == "edit"
    result = execute_natural_query(session_id, user_query, is_edit=is_edit)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@app.post("/api/confirm-edit/{session_id}")
def confirm_edit(session_id: str, sql_query: str = Query(...)):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    result = confirm_and_execute_edit(session_id, sql_query)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result