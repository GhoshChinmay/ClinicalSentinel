"""
DataSentinel — FastAPI Application
API routes, file upload handling, and session management.
"""

import os

# Load .env file before anything else reads environment variables
from dotenv import load_dotenv

load_dotenv()

# Bypass Loky/Joblib CPU counting bug on Windows that causes ValueError: 0 physical cores < 1
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
# Prevent OpenMP and BLAS from spawning hundreds of threads, which deadlocks Polars on Windows
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import polars as pl
from fastapi import FastAPI, UploadFile, File, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from utils import (
    _session_dir,
    _BACKEND_DIR,
    logger,
    validate_session_id,
    cleanup_stale_sessions,
)
from schema import SchemaEnforcer
from auth import require_api_key, is_auth_enabled
from engines import (
    process_and_detect,
    clean_dataset,
    get_viz_data,
    generate_insights,
    execute_natural_query,
    confirm_and_execute_edit,
    generate_quality_report,
    scan_for_pii,
    pseudonymise_columns,
)

# --- RATE LIMITER (in-memory, per-IP) ----------------------------------------
limiter = Limiter(key_func=get_remote_address)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

logger.info(
    "Auth: %s | Rate limiting: enabled",
    "ENABLED (DS_API_KEY is set)" if is_auth_enabled() else "DISABLED (no DS_API_KEY)",
)


class FeedbackRequest(BaseModel):
    session_id: str
    row_data: dict
    is_correct: bool


@app.post("/api/feedback/", dependencies=[Depends(require_api_key)])
@limiter.limit("120/minute")
def submit_feedback(request: Request, payload: FeedbackRequest):
    import json

    feedback_file = os.path.join(_BACKEND_DIR, "data", "feedback.jsonl")
    os.makedirs(os.path.dirname(feedback_file), exist_ok=True)
    # H-01 FIX: Prevent oversized row_data from being written to disk (DoS via write amplification)
    payload_bytes = json.dumps(payload.row_data).encode()
    MAX_FEEDBACK_BYTES = 64 * 1024  # 64 KB per feedback entry is more than enough
    if len(payload_bytes) > MAX_FEEDBACK_BYTES:
        return JSONResponse(
            status_code=413, content={"error": "Feedback payload too large."}
        )
    with open(feedback_file, "a") as f:
        # BUG-08 FIX: .dict() is deprecated in Pydantic v2; use .model_dump()
        f.write(json.dumps(payload.model_dump()) + "\n")
    return {"status": "success"}


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


@app.get("/api/health")
def health_check():
    """Verify Groq Cloud API connectivity for the frontend."""
    from groq_client import check_groq_connectivity

    connected = check_groq_connectivity()
    return {"groq": connected, "engine": "Groq LPU Cloud"}


@app.post("/api/upload/", dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
async def upload_csv(request: Request, file: UploadFile = File(...)):
    # Clean up stale sessions (>24h old) instead of nuking everything
    cleanup_stale_sessions(max_age_hours=24)

    os.makedirs(os.path.join(_BACKEND_DIR, "temp_uploads"), exist_ok=True)
    # BUG-07 FIX: Sanitize filename to prevent path traversal attacks (e.g. ../../etc/passwd)
    safe_filename = os.path.basename(file.filename or "upload.bin")
    if not safe_filename:
        safe_filename = "upload.bin"
    temp_file_path = os.path.join(_BACKEND_DIR, "temp_uploads", safe_filename)

    try:
        contents = await file.read()

        # --- INCREASED LIMIT: 100MB -> 500MB ---
        # SAFE-01 FIX: Reject files over 500MB before writing to disk (prevents OOM)
        MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB
        if len(contents) > MAX_UPLOAD_BYTES:
            return JSONResponse(
                status_code=413,
                content={
                    "error": f"File too large ({len(contents) // (1024*1024)} MB). Maximum upload size is 500 MB."
                },
            )

        with open(temp_file_path, "wb") as f:
            f.write(contents)

        # ── MULTI-FORMAT PARSER ──────────────────────────────────────────────
        filename_lower = safe_filename.lower()
        df = None

        # 1. Handle WASM Edge Parquet Payload
        if filename_lower.endswith(".parquet"):
            try:
                df = pl.read_parquet(temp_file_path)
                logger.info("Parsed Secure Parquet payload: %s", file.filename)
            except Exception as e:
                return JSONResponse(
                    status_code=400, content={"error": f"Parquet parse failed: {str(e)}"}
                )

        # 2. Handle Excel Fallback
        elif filename_lower.endswith((".xlsx", ".xls")):
            try:
                import pandas as pd

                pandas_df = pd.read_excel(temp_file_path, engine="openpyxl")
                df = pl.from_pandas(pandas_df)
                logger.info("Parsed Excel file: %s", file.filename)
            except Exception as e:
                return JSONResponse(
                    status_code=400, content={"error": f"Excel parse failed: {str(e)}"}
                )

        elif filename_lower.endswith(".json"):
            try:
                import json
                import pandas as pd

                with open(temp_file_path, "r") as jf:
                    raw = json.load(jf)
                if isinstance(raw, list):
                    df = pl.from_pandas(pd.DataFrame(raw))
                elif isinstance(raw, dict):
                    # Try common wrappers: {"data": [...]}
                    for key in ["data", "records", "rows", "items"]:
                        if key in raw and isinstance(raw[key], list):
                            df = pl.from_pandas(pd.DataFrame(raw[key]))
                            break
                if df is None:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": "JSON must be an array of objects or {data: [...]}."
                        },
                    )
                logger.info("Parsed JSON file: %s", file.filename)
            except Exception as e:
                return JSONResponse(
                    status_code=400, content={"error": f"JSON parse failed: {str(e)}"}
                )

        else:
            # Default: CSV with resilient fallback
            try:
                df = pl.read_csv(temp_file_path, infer_schema_length=1_000_000)
            except Exception:
                try:
                    import pandas as pd

                    df = pl.from_pandas(pd.read_csv(temp_file_path, low_memory=False))
                except Exception as inner_e:
                    return JSONResponse(
                        status_code=500,
                        content={"error": f"Fatal read error: {str(inner_e)}"},
                    )

        validation = SchemaEnforcer.validate(df, dataset_name=file.filename)
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


# ── NEW: PII SCANNER ROUTES ──────────────────────────────────────────────────
@app.get("/api/pii-scan/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("120/minute")
def pii_scan(request: Request, session_id: str):
    """Run PII detection on the uploaded dataset before analysis."""
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    session_dir = _session_dir(session_id)
    raw_path = f"{session_dir}/raw_data.parquet"

    if not os.path.exists(raw_path):
        return JSONResponse(status_code=404, content={"error": "Dataset not found"})

    df = pl.read_parquet(raw_path)
    findings = scan_for_pii(df)
    return {"findings": findings, "pii_detected": len(findings) > 0}


@app.post("/api/pseudonymise/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("60/minute")
def pseudonymise(request: Request, session_id: str, columns: list[str]):
    """Hash-pseudonymise specified PII columns in the stored dataset."""
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    session_dir = _session_dir(session_id)
    raw_path = f"{session_dir}/raw_data.parquet"

    if not os.path.exists(raw_path):
        return JSONResponse(status_code=404, content={"error": "Dataset not found"})

    df = pl.read_parquet(raw_path)
    df = pseudonymise_columns(df, columns)

    # Overwrite the raw data with the safe, hashed version
    df.write_parquet(raw_path)

    # Re-run detection to update anomaly scores with hashed data
    result = process_and_detect(df=df, session_id=session_id)

    return {
        "status": "success",
        "pseudonymised_columns": columns,
        "message": f"Salted SHA-256 pseudonymisation applied to {len(columns)} columns.",
        "detection_result": result,
    }


# ─────────────────────────────────────────────────────────────────────────────


@app.get("/api/data/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("120/minute")
def get_data(
    request: Request,
    session_id: str,
    is_cleaned: bool = Query(False),
    only_anomalies: bool = Query(False),
    limit: int = Query(1000),
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

        # Sort anomalies by Threat_Score descending so that the top severe ones (which have SHAP/AI reasoning) appear first on the UI
        if "Threat_Score" in anomalies.columns:
            anomalies = anomalies.sort("Threat_Score", descending=True)

        total_anomalies = len(anomalies)
        if only_anomalies:
            df = anomalies

    # Prevent out of memory errors by capping json payload
    total_rows = len(df)
    if total_rows > limit:
        df = df.head(limit)

    return {
        "data": df.to_dicts(),
        "total_anomalies": total_anomalies,
        "total_rows": total_rows,  # To let frontend know actual count
    }


@app.post("/api/clean/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("120/minute")
def clean_data(request: Request, session_id: str, action: str = Query("drop")):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    result = clean_dataset(session_id, action)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/api/compare/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("120/minute")
def compare_data(request: Request, session_id: str):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    session_dir = _session_dir(session_id)
    raw_path = f"{session_dir}/raw_data.parquet"
    clean_path = f"{session_dir}/cleaned_data.parquet"

    if not os.path.exists(clean_path):
        return JSONResponse(
            status_code=400, content={"error": "No cleaned data found."}
        )
    # SAFE-03 FIX: Also verify the raw data file exists before reading it
    if not os.path.exists(raw_path):
        return JSONResponse(
            status_code=400,
            content={"error": "Raw dataset not found. Session may be corrupted."},
        )

    df_raw = pl.read_parquet(raw_path)
    df_clean = pl.read_parquet(clean_path)

    is_dropped = len(df_clean) < len(df_raw)

    internal_cols = {"is_anomaly", "Threat_Score", "AI_Reason"}
    engineered_suffixes = (
        "_freq",
        "_length",
        "_digit_ratio",
        "_upper_ratio",
        "_special_ratio",
    )
    engineered_prefixes = ("nlp_pc",)
    velocity_names = {"velocity_24h_sum", "velocity_1h_count"}

    cols_to_drop = [
        c
        for c in df_raw.columns
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


@app.get("/api/viz/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("120/minute")
def viz_data(request: Request, session_id: str):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    result = get_viz_data(session_id)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/api/insights/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("20/minute")
def insights(request: Request, session_id: str):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    result = generate_insights(session_id)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/api/report/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("20/minute")
def report(request: Request, session_id: str):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    result = generate_quality_report(session_id)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/api/download/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("120/minute")
def download_data(request: Request, session_id: str, source: str = Query("cleaned")):
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
        return JSONResponse(
            status_code=404, content={"error": f"No {source} data found."}
        )

    df = pl.read_parquet(parquet_path)

    # SAFE-04 FIX: Strip ALL internal/engineered columns (not just is_anomaly/Threat_Score/AI_Reason)
    internal_cols_set = {"is_anomaly", "Threat_Score", "AI_Reason", "SHAP_Payload"}
    engineered_suffixes = (
        "_freq",
        "_length",
        "_digit_ratio",
        "_upper_ratio",
        "_special_ratio",
    )
    engineered_prefixes = ("nlp_pc",)
    velocity_names = {"velocity_24h_sum", "velocity_1h_count"}
    cols_to_drop = [
        c
        for c in df.columns
        if c in internal_cols_set
        or c.endswith(engineered_suffixes)
        or any(c.startswith(p) for p in engineered_prefixes)
        or c in velocity_names
    ]
    if cols_to_drop:
        df = df.drop(cols_to_drop)

    csv_path = f"{session_dir}/{csv_filename}"
    df.write_csv(csv_path)

    return FileResponse(path=csv_path, media_type="text/csv", filename=csv_filename)


@app.get("/api/quarantine/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("120/minute")
def get_quarantine(request: Request, session_id: str, limit: int = Query(1000)):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    session_dir = _session_dir(session_id)
    quarantine_path = f"{session_dir}/quarantined_data.parquet"

    if not os.path.exists(quarantine_path):
        return {"data": [], "count": 0}

    df = pl.read_parquet(quarantine_path)
    total_count = len(df)

    if total_count > limit:
        df = df.head(limit)

    return {"data": df.to_dicts(), "count": total_count}


@app.post("/api/query/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("20/minute")
def query_data(
    request: Request,
    session_id: str,
    user_query: str = Query(...),
    mode: str = Query("explore"),
):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    is_edit = mode == "edit"
    result = execute_natural_query(session_id, user_query, is_edit=is_edit)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@app.post("/api/confirm-edit/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("20/minute")
def confirm_edit(request: Request, session_id: str, sql_query: str = Query(...)):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    result = confirm_and_execute_edit(session_id, sql_query)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/api/samples")  # Public — no auth required
@limiter.limit("120/minute")
def list_samples(request: Request):
    """Returns available built-in sample datasets."""
    data_dir = os.path.join(_BACKEND_DIR, "data")
    samples = []
    descriptions = {
        "fraud_transactions.csv": {
            "name": "Financial Fraud Transactions",
            "rows": 500,
            "anomalies": 25,
            "description": "Synthetic bank transactions with offshore fraud patterns.",
            "icon": "💳",
        },
        "patient_vitals.csv": {
            "name": "Patient Vitals Monitor",
            "rows": 300,
            "anomalies": 15,
            "description": "ICU sensor readings with equipment glitch anomalies.",
            "icon": "🏥",
        },
        "ecommerce_reviews.csv": {
            "name": "E-Commerce Reviews",
            "rows": 400,
            "anomalies": 20,
            "description": "Product reviews with bot-generated spam injected.",
            "icon": "🛒",
        },
    }
    for fname, meta in descriptions.items():
        fpath = os.path.join(data_dir, fname)
        if os.path.exists(fpath):
            samples.append({**meta, "filename": fname})
    return {"samples": samples}


@app.post("/api/load-sample/{filename}", dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
async def load_sample(request: Request, filename: str):
    """Loads a built-in sample dataset through the full detection pipeline."""
    # Sanitise filename — only allow known files
    allowed = {"fraud_transactions.csv", "patient_vitals.csv", "ecommerce_reviews.csv"}
    if filename not in allowed:
        return JSONResponse(status_code=400, content={"error": "Unknown sample file."})

    data_dir = os.path.join(_BACKEND_DIR, "data")
    file_path = os.path.join(data_dir, filename)

    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "Sample not found."})

    try:
        df = pl.read_csv(file_path, infer_schema_length=1_000_000)
        validation = SchemaEnforcer.validate(df, dataset_name=filename)
        if not validation["valid"]:
            return JSONResponse(
                status_code=400, content={"errors": validation["errors"]}
            )
        result = process_and_detect(df=df, file_path=file_path)
        return result
    except Exception as e:
        logger.error("Sample load failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
