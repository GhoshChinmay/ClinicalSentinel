# DataSentinel End-to-End Stress Test Report
**Dataset**: `creditcard.csv`
**File Size**: 156.78 MB
---

## 1. Upload & Anomaly Detection Pipeline
- **Status**: ✅ Success
- **Time taken**: 111.98 seconds
- **Session ID**: `e00ba0a2-b517-4bf9-927d-2cb2ca8906aa`
- **Anomalies Detected**: None
- **Total Rows**: 284807

## 2. PII Scan
- **Status**: ✅ Success
- **Time taken**: 2.21 seconds
- **PII Detected**: True (1 findings)

## 3. Data Pagination/Fetch (Limit: 1000)
- **Status**: ✅ Success
- **Time taken**: 2.32 seconds
- **Rows Fetched**: 1000

## 4. LLM Insights Generation
- **Status**: ✅ Success
- **Time taken**: 7.23 seconds

## 5. Cleaning Subsystem (Action: drop)
- **Status**: ✅ Success
- **Time taken**: 2.56 seconds
- **Clean Rows Count**: None

## 6. Compare Feature
- **Status**: ✅ Success
- **Time taken**: 2.55 seconds

## 7. Visualization Data Aggregation
- **Status**: ✅ Success
- **Time taken**: 5.97 seconds

## 8. Export Quality Report
- **Status**: ✅ Success
- **Time taken**: 2.42 seconds