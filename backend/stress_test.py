import os
import time
import requests
import json
import logging

BASE_URL = "http://localhost:8000"
DATASET_PATH = os.path.join(os.path.dirname(__file__), "data", "creditcard.csv")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "stress_test_report.md")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

report_lines = []
def log_and_report(msg):
    logging.info(msg)
    report_lines.append(msg)

def run_stress_test():
    log_and_report("# DataSentinel End-to-End Stress Test Report")
    log_and_report(f"**Dataset**: `creditcard.csv`")
    log_and_report(f"**File Size**: {os.path.getsize(DATASET_PATH) / (1024*1024):.2f} MB")
    log_and_report("---\n")
    
    session_id = None
    
    # 1. Upload
    log_and_report("## 1. Upload & Anomaly Detection Pipeline")
    try:
        start_time = time.time()
        with open(DATASET_PATH, "rb") as f:
            files = {"file": ("creditcard.csv", f, "text/csv")}
            logging.info("Initiating upload. This may take a while as the isolation forest computes globally...")
            response = requests.post(f"{BASE_URL}/api/upload/", files=files)
        
        duration = time.time() - start_time
        if response.status_code == 200:
            data = response.json()
            session_id = data.get("session_id")
            log_and_report(f"- **Status**: ✅ Success")
            log_and_report(f"- **Time taken**: {duration:.2f} seconds")
            log_and_report(f"- **Session ID**: `{session_id}`")
            log_and_report(f"- **Anomalies Detected**: {data.get('total_anomalies')}")
            log_and_report(f"- **Total Rows**: {data.get('total_rows')}")
        else:
            log_and_report(f"- **Status**: ❌ Failed ({response.status_code})")
            log_and_report(f"- **Details**: {response.text}")
            return
    except Exception as e:
        log_and_report(f"- **Status**: ❌ Exception: {str(e)}")
        return

    # 2. PII Scan
    log_and_report("\n## 2. PII Scan")
    try:
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/api/pii-scan/{session_id}")
        duration = time.time() - start_time
        if response.status_code == 200:
            data = response.json()
            log_and_report(f"- **Status**: ✅ Success")
            log_and_report(f"- **Time taken**: {duration:.2f} seconds")
            log_and_report(f"- **PII Detected**: {data.get('pii_detected')} ({len(data.get('findings', []))} findings)")
        else:
            log_and_report(f"- **Status**: ❌ Failed ({response.status_code}) - {response.text}")
    except Exception as e:
        log_and_report(f"- **Status**: ❌ Exception: {str(e)}")

    # 3. Data Fetch
    log_and_report("\n## 3. Data Pagination/Fetch (Limit: 1000)")
    try:
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/api/data/{session_id}")
        duration = time.time() - start_time
        if response.status_code == 200:
            data = response.json()
            log_and_report(f"- **Status**: ✅ Success")
            log_and_report(f"- **Time taken**: {duration:.2f} seconds")
            log_and_report(f"- **Rows Fetched**: {len(data.get('data', []))}")
        else:
            log_and_report(f"- **Status**: ❌ Failed ({response.status_code}) - {response.text}")
    except Exception as e:
        log_and_report(f"- **Status**: ❌ Exception: {str(e)}")

    # 4. Insights Generation (Groq/LLM)
    log_and_report("\n## 4. LLM Insights Generation")
    try:
        start_time = time.time()
        logging.info("Calling /api/insights/...")
        response = requests.get(f"{BASE_URL}/api/insights/{session_id}")
        duration = time.time() - start_time
        if response.status_code == 200:
            log_and_report(f"- **Status**: ✅ Success")
            log_and_report(f"- **Time taken**: {duration:.2f} seconds")
        else:
            log_and_report(f"- **Status**: ❌ Failed ({response.status_code}) - {response.text}")
    except Exception as e:
        log_and_report(f"- **Status**: ❌ Exception: {str(e)}")

    # 5. Clean / Drop Anomalies
    log_and_report("\n## 5. Cleaning Subsystem (Action: drop)")
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/clean/{session_id}?action=drop")
        duration = time.time() - start_time
        if response.status_code == 200:
            data = response.json()
            log_and_report(f"- **Status**: ✅ Success")
            log_and_report(f"- **Time taken**: {duration:.2f} seconds")
            log_and_report(f"- **Clean Rows Count**: {data.get('count')}")
        else:
            log_and_report(f"- **Status**: ❌ Failed ({response.status_code}) - {response.text}")
    except Exception as e:
        log_and_report(f"- **Status**: ❌ Exception: {str(e)}")

    # 6. Compare Dataset
    log_and_report("\n## 6. Compare Feature")
    try:
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/api/compare/{session_id}")
        duration = time.time() - start_time
        if response.status_code == 200:
            log_and_report(f"- **Status**: ✅ Success")
            log_and_report(f"- **Time taken**: {duration:.2f} seconds")
        else:
            log_and_report(f"- **Status**: ❌ Failed ({response.status_code}) - {response.text}")
    except Exception as e:
        log_and_report(f"- **Status**: ❌ Exception: {str(e)}")

    # 7. Viz Feature
    log_and_report("\n## 7. Visualization Data Aggregation")
    try:
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/api/viz/{session_id}")
        duration = time.time() - start_time
        if response.status_code == 200:
            log_and_report(f"- **Status**: ✅ Success")
            log_and_report(f"- **Time taken**: {duration:.2f} seconds")
        else:
            log_and_report(f"- **Status**: ❌ Failed ({response.status_code}) - {response.text}")
    except Exception as e:
        log_and_report(f"- **Status**: ❌ Exception: {str(e)}")

    # 8. Report Generation
    log_and_report("\n## 8. Export Quality Report")
    try:
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/api/report/{session_id}")
        duration = time.time() - start_time
        if response.status_code == 200:
            log_and_report(f"- **Status**: ✅ Success")
            log_and_report(f"- **Time taken**: {duration:.2f} seconds")
        else:
            log_and_report(f"- **Status**: ❌ Failed ({response.status_code}) - {response.text}")
    except Exception as e:
        log_and_report(f"- **Status**: ❌ Exception: {str(e)}")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    logging.info(f"Done. Report saved to {REPORT_PATH}")

if __name__ == "__main__":
    run_stress_test()
