# DataSentinel End-to-End Stress Test Report
**Dataset**: `creditcard.csv`
**File Size**: 156.78 MB
---

## 1. Upload & Anomaly Detection Pipeline
- **Status**: ✅ Success
- **Time taken**: 87.51 seconds
- **Session ID**: `0e712b27-fb36-4989-8eb7-c777c9b1877e`
- **Anomalies Detected**: None
- **Total Rows**: 284807

## 2. PII Scan
- **Status**: ✅ Success
- **Time taken**: 2.22 seconds
- **PII Detected**: True (1 findings)

## 3. Data Pagination/Fetch (Limit: 1000)
- **Status**: ✅ Success
- **Time taken**: 2.39 seconds
- **Rows Fetched**: 1000

## 4. LLM Insights Generation
- **Status**: ✅ Success
- **Time taken**: 4.63 seconds

## 5. Cleaning Subsystem (Action: drop)
- **Status**: ✅ Success
- **Time taken**: 2.25 seconds
- **Clean Rows Count**: None

## 6. Compare Feature
- **Status**: ✅ Success
- **Time taken**: 2.19 seconds

## 7. Visualization Data Aggregation
- **Status**: ✅ Success
- **Time taken**: 3.28 seconds

## 8. Export Quality Report
- **Status**: ✅ Success
- **Time taken**: 2.22 seconds