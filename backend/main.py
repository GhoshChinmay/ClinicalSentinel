"""
ClinicalSentinel — FastAPI Application
API routes, file upload handling, and session management.
"""

import os
import re
import json

# Load .env file before anything else reads environment variables
from dotenv import load_dotenv
import io

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
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
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
    execute_natural_query_stream,
    confirm_and_execute_edit,
    generate_quality_report,
    scan_for_pii,
    pseudonymise_columns,
    # F1–F7 Clinical Intelligence Layers
    calculate_composite_fri,
    calculate_fri_report,
    detect_behavioral_anomalies,
    audit_against_synthetic,
    detect_cohort_drift,
    evaluate_compliance,
    initialize_regulatory_knowledge_base,
    authenticate_wearable_data,
    detect_collusion_networks,
    GNN_AVAILABLE,
    generate_21cfr_pdf,
    decompose_shap_to_layers,
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
    payload_bytes = json.dumps(payload.row_data).encode()
    MAX_FEEDBACK_BYTES = 64 * 1024  
    if len(payload_bytes) > MAX_FEEDBACK_BYTES:
        return JSONResponse(
            status_code=413, content={"error": "Feedback payload too large."}
        )
    with open(feedback_file, "a") as f:
        f.write(json.dumps(payload.model_dump()) + "\n")
    return {"status": "success"}


class KnowledgeRule(BaseModel):
    term: str
    logic: str
    description: str
    keywords: list[str]

@app.post("/api/knowledge/learn", dependencies=[Depends(require_api_key)])
@limiter.limit("20/minute")
def teach_agent(request: Request, payload: KnowledgeRule):
    dict_path = os.path.join(_BACKEND_DIR, "data", "business_dictionary.json")
    
    if not os.path.exists(dict_path):
        kb_data = {"version": "2.0.0", "knowledge_base": {"user_defined": []}}
    else:
        with open(dict_path, "r") as f:
            kb_data = json.load(f)
            
    if "user_defined" not in kb_data["knowledge_base"]:
        kb_data["knowledge_base"]["user_defined"] = []

    new_rule = {
        "term": payload.term,
        "keywords": payload.keywords,
        "logic": payload.logic,
        "description": payload.description
    }
    kb_data["knowledge_base"]["user_defined"].append(new_rule)

    os.makedirs(os.path.dirname(dict_path), exist_ok=True)
    with open(dict_path, "w") as f:
        json.dump(kb_data, f, indent=2)

    return {"status": "success", "message": f"Agent successfully learned the rule for '{payload.term}'."}


class DBConnectionRequest(BaseModel):
    uri: str 

@app.post("/api/connect-db/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
def connect_postgres(request: Request, session_id: str, payload: DBConnectionRequest):
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    if not payload.uri.startswith(("postgres://", "postgresql://")):
        return JSONResponse(status_code=400, content={"error": "Only PostgreSQL URIs are supported in this version."})

    session_dir = _session_dir(session_id)
    config_path = os.path.join(session_dir, "db_config.json")

    with open(config_path, "w") as f:
        json.dump({"db_uri": payload.uri, "type": "postgres"}, f)

    return {"status": "success", "message": "PostgreSQL Database successfully linked."}


@app.get("/api/admin/audit-logs", dependencies=[Depends(require_api_key)])
@limiter.limit("30/minute")
def get_audit_logs(request: Request, limit: int = Query(100)):
    audit_file = os.path.join(_BACKEND_DIR, "logs", "audit_trail.jsonl")
    
    if not os.path.exists(audit_file):
        return {"logs": []}
        
    logs = []
    try:
        with open(audit_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))
        return {"logs": list(reversed(logs))[:limit]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Failed to read logs: {str(e)}"})


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
    return {"status": "ClinicalSentinel Forensic Audit Engine is online."}


@app.get("/api/health")
def health_check():
    from groq_client import check_groq_connectivity
    connected = check_groq_connectivity()
    return {"groq": connected, "engine": "Groq LPU Cloud"}


@app.post("/api/upload/", dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
async def upload_csv(request: Request, file: UploadFile = File(...)):
    cleanup_stale_sessions(max_age_hours=24)
    os.makedirs(os.path.join(_BACKEND_DIR, "temp_uploads"), exist_ok=True)
    
    safe_filename = os.path.basename(file.filename or "upload.bin")
    if not safe_filename:
        safe_filename = "upload.bin"
    temp_file_path = os.path.join(_BACKEND_DIR, "temp_uploads", safe_filename)

    try:
        contents = await file.read()
        MAX_UPLOAD_BYTES = 500 * 1024 * 1024  
        if len(contents) > MAX_UPLOAD_BYTES:
            return JSONResponse(
                status_code=413,
                content={"error": f"File too large ({len(contents) // (1024*1024)} MB). Maximum upload size is 500 MB."},
            )

        with open(temp_file_path, "wb") as f:
            f.write(contents)

        filename_lower = safe_filename.lower()
        df = None

        if filename_lower.endswith(".parquet"):
            try:
                df = pl.read_parquet(temp_file_path)
                logger.info("Parsed Secure Parquet payload: %s", file.filename)
            except Exception as e:
                return JSONResponse(status_code=400, content={"error": f"Parquet parse failed: {str(e)}"})

        elif filename_lower.endswith((".xlsx", ".xls")):
            try:
                import pandas as pd
                pandas_df = pd.read_excel(temp_file_path, engine="openpyxl")
                df = pl.from_pandas(pandas_df)
                logger.info("Parsed Excel file: %s", file.filename)
            except Exception as e:
                return JSONResponse(status_code=400, content={"error": f"Excel parse failed: {str(e)}"})

        elif filename_lower.endswith(".json"):
            try:
                import json
                import pandas as pd
                with open(temp_file_path, "r") as jf:
                    raw = json.load(jf)
                if isinstance(raw, list):
                    df = pl.from_pandas(pd.DataFrame(raw))
                elif isinstance(raw, dict):
                    for key in ["data", "records", "rows", "items"]:
                        if key in raw and isinstance(raw[key], list):
                            df = pl.from_pandas(pd.DataFrame(raw[key]))
                            break
                if df is None:
                    return JSONResponse(status_code=400, content={"error": "JSON must be an array of objects or {data: [...]}."})
                logger.info("Parsed JSON file: %s", file.filename)
            except Exception as e:
                return JSONResponse(status_code=400, content={"error": f"JSON parse failed: {str(e)}"})

        else:
            try:
                df = pl.read_csv(temp_file_path, infer_schema_length=1_000_000)
            except Exception:
                try:
                    import pandas as pd
                    df = pl.from_pandas(pd.read_csv(temp_file_path, low_memory=False))
                except Exception as inner_e:
                    return JSONResponse(status_code=400, content={"error": f"Fatal read error (invalid or corrupted file): {str(inner_e)}"})

        validation = SchemaEnforcer.validate(df, dataset_name=file.filename)
        if not validation["valid"]:
            return JSONResponse(status_code=400, content={"status": "rejected", "errors": validation["errors"]})

        result = process_and_detect(df=df, file_path=temp_file_path)

        if isinstance(result, dict) and result.get("session_id"):
            _meta_path = os.path.join(_session_dir(result["session_id"]), "detection_meta.json")
            try:
                with open(_meta_path, "w") as _mf:
                    json.dump(
                        {"drift_report": result.get("drift_report"), "recommendation": result.get("recommendation")},
                        _mf,
                    )
            except Exception:
                pass 

        return result

    except Exception as e:
        logger.error("Upload failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@app.get("/api/pii-scan/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("120/minute")
def pii_scan(request: Request, session_id: str):
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

    df.write_parquet(raw_path)
    result = process_and_detect(df=df, session_id=session_id)

    return {
        "status": "success",
        "pseudonymised_columns": columns,
        "message": f"Salted SHA-256 pseudonymisation applied to {len(columns)} columns.",
        "detection_result": result,
    }


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
        if "Threat_Score" in anomalies.columns:
            anomalies = anomalies.sort("Threat_Score", descending=True)
        total_anomalies = len(anomalies)
        if only_anomalies:
            df = anomalies

    total_rows = len(df)
    if total_rows > limit:
        df = df.head(limit)

    detection_meta: dict = {}
    meta_path = os.path.join(session_dir, "detection_meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as mf:
                detection_meta = json.load(mf)
        except Exception:
            pass

    return {
        "data": df.to_dicts(),
        "total_anomalies": total_anomalies,
        "total_rows": total_rows, 
        "drift_report": detection_meta.get("drift_report"),
        "recommendation": detection_meta.get("recommendation"),
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
        return JSONResponse(status_code=400, content={"error": "No cleaned data found."})
    if not os.path.exists(raw_path):
        return JSONResponse(status_code=400, content={"error": "Raw dataset not found. Session may be corrupted."})

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


# ── NEW: ENDPOINT TO DOWNLOAD THE FDA 21 CFR COMPLIANT PDF ──
@app.get("/api/download_report/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("20/minute")
def download_audit_report(request: Request, session_id: str):
    """Serve the 21 CFR Part 11 PDF Audit Report generated by the Insights engine."""
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    session_dir = _session_dir(session_id)
    pdf_path = os.path.join(session_dir, "clinical_audit_report.pdf")

    if not os.path.exists(pdf_path):
        return JSONResponse(status_code=404, content={"error": "Audit report not found. Please run the Insights engine first."})

    return FileResponse(
        path=pdf_path,
        filename=f"ClinicalSentinel_Audit_{session_id[:8]}.pdf",
        media_type="application/pdf"
    )


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
        return JSONResponse(status_code=404, content={"error": f"No {source} data found."})

    df = pl.read_parquet(parquet_path)

    internal_cols_set = {
        "is_anomaly", "Threat_Score", "AI_Reason", "SHAP_Payload", 
        "Counterfactual_Payload", "lof_score", "lstm_anomaly_score", "ecod_score"
    }
    engineered_suffixes = ("_freq", "_length", "_digit_ratio", "_upper_ratio", "_special_ratio")
    engineered_prefixes = ("nlp_pc",)
    velocity_names = {"velocity_24h_sum", "velocity_1h_count"}
    
    cols_to_drop = [
        c for c in df.columns
        if c in internal_cols_set
        or c.startswith("Score_CI")
        or c.endswith(engineered_suffixes)
        or any(c.startswith(p) for p in engineered_prefixes)
        or c in velocity_names
    ]
    if cols_to_drop:
        df = df.drop([c for c in cols_to_drop if c in df.columns])

    buffer = io.BytesIO()
    df.write_csv(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer, 
        media_type="text/csv", 
        headers={"Content-Disposition": f'attachment; filename="{csv_filename}"'}
    )


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
async def query_data(
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
    return StreamingResponse(
        execute_natural_query_stream(session_id, user_query, is_edit=is_edit),
        media_type="text/event-stream"
    )

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


# =============================================================================
# CLINICAL INTELLIGENCE LAYER ENDPOINTS (F1 – F7)
# =============================================================================

@app.get("/api/clinical/xfri/{session_id}/row/{row_index}", dependencies=[Depends(require_api_key)])
@limiter.limit("30/minute")
def run_xfri_row(request: Request, session_id: str, row_index: int):
    """
    F1: X-FRI Explainer — Decomposes a specific anomalous row's SHAP payload
    into the 7 clinical forensic layers.
    """
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    raw_path = os.path.join(_session_dir(session_id), "raw_data.parquet")
    if not os.path.exists(raw_path):
        return JSONResponse(status_code=404, content={"error": "Dataset not found."})

    try:
        df = pl.read_parquet(raw_path)
        row = df.row(row_index, named=True)
        shap_str = row.get("SHAP_Payload", "[]")
        logic_violation = row.get("logic_violation", None)
        result = decompose_shap_to_layers(shap_str, str(logic_violation) if logic_violation else None)
        return result
    except Exception as e:
        logger.error("X-FRI failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


class FRIRequest(BaseModel):
    investigator_col: str
    time_col: str | None = None
    metric_cols: list[str] = []
    shared_attr_cols: list[str] = []


@app.post("/api/clinical/fri/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
def run_fri(request: Request, session_id: str, payload: FRIRequest):
    """
    F1–F7 COMPOSITE: Runs all forensic layers and returns per-investigator
    Fabrication Risk Index (FRI) scores. The core patentable output.
    """
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    raw_path = os.path.join(_session_dir(session_id), "raw_data.parquet")
    if not os.path.exists(raw_path):
        return JSONResponse(status_code=404, content={"error": "Dataset not found. Upload a file first."})

    try:
        df = pl.read_parquet(raw_path)
        result = calculate_composite_fri(
            df=df,
            investigator_col=payload.investigator_col,
            time_col=payload.time_col,
            metric_cols=payload.metric_cols,
            shared_attr_cols=payload.shared_attr_cols,
        )
        return result
    except Exception as e:
        logger.error("FRI calculation failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/clinical/fri/auto/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
def run_fri_auto(request: Request, session_id: str):
    """
    Auto-detect wrapper for FRI. Does not require a POST payload.
    Automatically searches for investigator/time/metric columns.
    """
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    raw_path = os.path.join(_session_dir(session_id), "raw_data.parquet")
    if not os.path.exists(raw_path):
        return JSONResponse(status_code=404, content={"error": "Dataset not found. Upload a file first."})

    try:
        df = pl.read_parquet(raw_path)
        result = calculate_fri_report(df)
        return result
    except Exception as e:
        logger.error("Auto FRI calculation failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/clinical/investi-profile/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
def run_investi_profile(
    request: Request,
    session_id: str,
    investigator_col: str = Query(...),
    time_col: str = Query(...),
):
    """
    F7: InvestiProfile — Longitudinal behavioral fingerprinting.
    Detects Behavioral Anomaly Events (BAEs): night shifts, speed-typing, data dumps.
    """
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    raw_path = os.path.join(_session_dir(session_id), "raw_data.parquet")
    if not os.path.exists(raw_path):
        return JSONResponse(status_code=404, content={"error": "Dataset not found."})

    try:
        df = pl.read_parquet(raw_path)
        result = detect_behavioral_anomalies(df, time_col, investigator_col)
        return {
            "status": "success",
            "flagged_investigators": len(result),
            "behavioral_reports": result,
        }
    except Exception as e:
        logger.error("InvestiProfile failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/clinical/cohort-drift/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
def run_cohort_drift(
    request: Request,
    session_id: str,
    investigator_col: str = Query(...),
    time_col: str = Query(...),
    metric_cols: str = Query(..., description="Comma-separated list of numeric metric columns"),
):
    """
    F5: CohortDrift — Intra-trial temporal cohort drift detector.
    Compares Phase 1 vs Phase 3 distributions using KS-Test and PSI.
    """
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    raw_path = os.path.join(_session_dir(session_id), "raw_data.parquet")
    if not os.path.exists(raw_path):
        return JSONResponse(status_code=404, content={"error": "Dataset not found."})

    try:
        df = pl.read_parquet(raw_path)
        cols = [c.strip() for c in metric_cols.split(",") if c.strip()]
        result = detect_cohort_drift(df, time_col, investigator_col, cols)
        return {
            "status": "success",
            "flagged_investigators": len(result),
            "drift_reports": result,
        }
    except Exception as e:
        logger.error("CohortDrift failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/clinical/synth-audit/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("5/minute")
def run_synth_audit(
    request: Request,
    session_id: str,
    investigator_col: str = Query(...),
    metric_cols: str = Query(..., description="Comma-separated list of continuous numeric columns"),
):
    """
    F6: SynthAudit — Generates a Gaussian Copula synthetic reference and measures
    each investigator's Synthetic Deviation Score (SDS) against it.
    """
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    raw_path = os.path.join(_session_dir(session_id), "raw_data.parquet")
    if not os.path.exists(raw_path):
        return JSONResponse(status_code=404, content={"error": "Dataset not found."})

    try:
        df = pl.read_parquet(raw_path)
        cols = [c.strip() for c in metric_cols.split(",") if c.strip()]
        result = audit_against_synthetic(df, investigator_col, cols)
        return {
            "status": "success",
            "flagged_investigators": len(result),
            "synth_audit_reports": result,
        }
    except Exception as e:
        logger.error("SynthAudit failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/clinical/wearable-gate/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
def run_wearable_gate(
    request: Request,
    session_id: str,
    patient_col: str = Query(...),
    time_col: str = Query(...),
    telemetry_cols: str = Query(..., description="Comma-separated list of wearable metric columns"),
):
    """
    F3: WearableGate — Authenticates wearable sensor data.
    Detects manual entry impersonating real hardware sensor output.
    """
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    raw_path = os.path.join(_session_dir(session_id), "raw_data.parquet")
    if not os.path.exists(raw_path):
        return JSONResponse(status_code=404, content={"error": "Dataset not found."})

    try:
        df = pl.read_parquet(raw_path)
        cols = [c.strip() for c in telemetry_cols.split(",") if c.strip()]
        result = authenticate_wearable_data(df, patient_col, time_col, cols)
        return {
            "status": "success",
            "flagged_patients": len(result),
            "wearable_reports": result,
        }
    except Exception as e:
        logger.error("WearableGate failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/clinical/gnn-collusion/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("5/minute")
def run_gnn_collusion(
    request: Request,
    session_id: str,
    investigator_col: str = Query(...),
    shared_attr_cols: str = Query(..., description="Comma-separated columns linking investigators (e.g., site_id,cro_id)"),
):
    """
    F2: GNN Collusion Detector — Builds an investigator relationship graph
    and propagates risk through a Graph Convolutional Network.
    """
    try:
        validate_session_id(session_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid session ID"})

    raw_path = os.path.join(_session_dir(session_id), "raw_data.parquet")
    if not os.path.exists(raw_path):
        return JSONResponse(status_code=404, content={"error": "Dataset not found."})

    try:
        df = pl.read_parquet(raw_path)
        pandas_df = df.to_pandas()
        cols = [c.strip() for c in shared_attr_cols.split(",") if c.strip()]
        
        # Run collusion detection
        result = detect_collusion_networks(df, investigator_col, cols)
        
        # Build graph structure for visualization even if GNN failed
        graph_nodes = []
        graph_edges = []
        collusion_reports = {}
        
        try:
            if investigator_col in pandas_df.columns:
                all_investigators = pandas_df[investigator_col].dropna().unique().tolist()
                collusion_reports = result if isinstance(result, dict) and "error" not in result and "status" not in result else {}
                
                graph_nodes = [
                    {
                        "id": str(inv),
                        "crcs": collusion_reports.get(str(inv), {}).get("CRCS_score", 0)
                    }
                    for inv in all_investigators
                ]
                
                # Build edges from shared attributes
                seen_edges = set()
                for attr_col in cols:
                    if attr_col not in pandas_df.columns:
                        continue
                    attr_groups = pandas_df.groupby(attr_col)[investigator_col].unique()
                    for shared_invs in attr_groups:
                        shared_list = [str(x) for x in shared_invs if str(x) != "nan"]
                        if len(shared_list) > 1:
                            for i, inv1 in enumerate(shared_list):
                                for inv2 in shared_list[i+1:]:
                                    edge_key = tuple(sorted([inv1, inv2]))
                                    if edge_key not in seen_edges:
                                        seen_edges.add(edge_key)
                                        graph_edges.append({"source": inv1, "target": inv2})
        except Exception as graph_err:
            logger.warning(f"Graph construction failed (non-fatal): {graph_err}")
        
        flagged_count = len(collusion_reports) if collusion_reports else 0
        
        return {
            "status": "success",
            "flagged_investigators": flagged_count,
            "collusion_reports": collusion_reports,
            "graph_nodes": graph_nodes,
            "graph_edges": graph_edges,
            "gnn_available": GNN_AVAILABLE,
        }

    except Exception as e:
        logger.error("GNN Collusion failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/clinical/reg-rag/init", dependencies=[Depends(require_api_key)])
@limiter.limit("3/minute")
def init_reg_rag(request: Request):
    """
    F4: RegRAG — Initializes the ChromaDB regulatory knowledge base.
    Indexes ICH E6(R3), 21 CFR Part 11, and DPDP Act 2023.
    Run this once before using the compliance evaluation endpoint.
    """
    try:
        collection = initialize_regulatory_knowledge_base()
        count = collection.count() if collection else 0
        return {
            "status": "success",
            "message": f"Regulatory knowledge base initialized with {count} indexed clauses.",
            "indexed_chunks": count,
        }
    except Exception as e:
        logger.error("RegRAG init failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


class RegRagEvalRequest(BaseModel):
    investigator_id: str
    anomaly_details: dict


@app.post("/api/clinical/reg-rag/evaluate", dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
def evaluate_reg_rag(request: Request, payload: RegRagEvalRequest):
    """
    F4: RegRAG — Evaluates a specific investigator's anomaly profile against
    indexed regulatory clauses and generates a compliance verdict.
    """
    try:
        result = evaluate_compliance(payload.investigator_id, payload.anomaly_details)
        return result
    except Exception as e:
        logger.error("RegRAG evaluate failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


# =============================================================================
# SAMPLE DATASETS (Updated for Clinical Sentinel)
# =============================================================================

@app.get("/api/samples") 
@limiter.limit("120/minute")
def list_samples(request: Request):
    """Returns available built-in sample datasets."""
    data_dir = os.path.join(_BACKEND_DIR, "data")
    samples = []
    descriptions = {
        "clinical_trial_sample.csv": {
            "name": "Clinical Trial Forensic Dataset",
            "rows": 690,
            "anomalies": 390,
            "description": "Multi-site EDC data with 6 embedded fraud patterns for FRI demo.",
            "icon": "🔬",
        },
        "wearable_telemetry_sample.csv": {
            "name": "Decentralized Trial Wearables",
            "rows": 1200,
            "anomalies": 80,
            "description": "Continuous heart rate telemetry with manual human injection.",
            "icon": "⌚",
        },
        "patient_vitals.csv": {
            "name": "Patient Vitals Monitor",
            "rows": 300,
            "anomalies": 15,
            "description": "ICU sensor readings with equipment glitch anomalies.",
            "icon": "🏥",
        },
    }
    for fname, meta in descriptions.items():
        fpath = os.path.join(data_dir, fname)
        # Check if file exists, or just return metadata so the UI has them ready
        if os.path.exists(fpath):
            samples.append({**meta, "filename": fname})
    return {"samples": samples}


@app.post("/api/load-sample/{filename}", dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
async def load_sample(request: Request, filename: str):
    """Loads a built-in sample dataset through the full detection pipeline."""
    allowed = {"patient_vitals.csv", "clinical_trial_sample.csv", "wearable_telemetry_sample.csv"}
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
            return JSONResponse(status_code=400, content={"errors": validation["errors"]})
        result = process_and_detect(df=df, file_path=file_path)
        return result
    except Exception as e:
        logger.error("Sample load failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/download_report/{session_id}", dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
def download_report(request: Request, session_id: str):
    """Generates and returns the 21 CFR Part 11 PDF audit report."""
    if not validate_session_id(session_id):
        return JSONResponse(status_code=400, content={"error": "Invalid session ID."})

    s_dir = _session_dir(session_id)
    fri_path = os.path.join(s_dir, "fri_analysis.json")
    if not os.path.exists(fri_path):
        return JSONResponse(status_code=404, content={"error": "FRI analysis not found for this session. Please run FRI analysis first."})

    try:
        with open(fri_path, "r") as f:
            fri_results = json.load(f)
            
        pdf_path = generate_21cfr_pdf(session_id, fri_results)
        
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"ClinicalSentinel_Audit_{session_id}.pdf"
        )
    except Exception as e:
        logger.error(f"Failed to generate PDF report: {e}")
        return JSONResponse(status_code=500, content={"error": f"Failed to generate report: {str(e)}"})