# DataSentinel — AI-Powered Data Quality Intelligence Platform
### Project Brief & Technical Documentation

---

**Team Project | Backend: Python · FastAPI · Scikit-learn · Polars | Frontend: Next.js 15 · TypeScript · Tailwind CSS**

---

## Abstract

DataSentinel is a full-stack, AI-powered data quality intelligence platform designed to automate the detection, diagnosis, and remediation of anomalies in structured datasets. Traditional data pipelines rely on manual inspection or simple rule-based validation, which fails at scale and cannot detect complex multi-variable patterns. DataSentinel solves this by applying a multi-modal detection pipeline — combining unsupervised machine learning (Isolation Forest), supervised classification (HistGradientBoosting), time-series velocity analysis, and NLP-based text anomaly detection — to any uploaded CSV dataset. The system then arms the user with five AI-recommended cleaning strategies, an interactive visualization suite, an LLM-powered insight engine, and a natural language SQL co-pilot, all delivered through a premium dark-mode web interface. The result is a platform that transforms raw, potentially corrupted data into a clean, auditable, and analyst-ready dataset in minutes rather than days.

---

## 1. Introduction

### 1.1 Purpose

The purpose of DataSentinel is to democratize data quality assurance. Organizations of every size — from startups to enterprises — suffer from poor data quality that silently corrupts analytical decisions, machine learning models, and business intelligence dashboards. DataSentinel provides a self-contained, locally-runnable intelligence layer that any user, regardless of technical expertise, can use to:

- Upload any CSV dataset and receive an immediate, detailed anomaly report
- Understand *why* a row is anomalous through plain-English AI explanations
- Apply one of five academically-grounded cleaning strategies with a single click
- Visualize statistical distributions before and after sanitization
- Query their dataset in natural language without writing SQL
- Export a clean, audited, and publication-ready dataset

### 1.2 Problem Statement

Modern data ecosystems face a critical and largely unsolved problem: **data quality degradation at ingestion**. Studies consistently show that data scientists spend 60–80% of their time on data cleaning rather than analysis or modelling. The root causes are:

1. **Scale**: Manual row-by-row inspection is infeasible for datasets with tens of thousands of records
2. **Complexity**: Single-column threshold checks miss multi-variate anomalies where individual values appear normal but the *combination* is statistically impossible
3. **Context blindness**: Existing tools treat all anomalies identically, regardless of whether the dataset is financial data, sensor telemetry, medical records, or e-commerce reviews
4. **Lack of auditability**: Most cleaning tools permanently destroy anomalous data with no forensic record, which is unacceptable in regulated industries
5. **Technical barrier**: SQL knowledge, Python scripting, or expensive BI subscriptions are gatekeepers for non-technical analysts

DataSentinel addresses all five of these failure modes in a single integrated platform.

### 1.3 Objectives

The primary objectives of DataSentinel are:

1. **Automate anomaly detection** using unsupervised and supervised machine learning across numerical, categorical, and textual data dimensions simultaneously
2. **Provide explainability** through human-readable AI-generated reasons for every anomaly, citing the specific columns and statistical deviations responsible
3. **Enable context-aware cleaning** by recommending the optimal sanitization strategy based on the detected domain (financial, medical, IoT, text-heavy, etc.)
4. **Preserve forensic integrity** through the Quarantine Vault — an audit log of all removed records — satisfying compliance requirements
5. **Surface insights automatically** using a local LLM (Ollama running Phi-3) to generate an OIA (Observation → Insight → Action) framework report on the dataset
6. **Enable natural language querying** through a DuckDB-powered SQL co-pilot that translates plain English questions into executed SQL queries with tabular results
7. **Deliver an excellent user experience** through a premium, animated, dark-mode web interface that guides the user step-by-step through the data quality pipeline

### 1.4 Scope

DataSentinel operates within the following scope:

- **Input**: CSV files of any size and domain (tested up to 150,000+ rows)
- **Processing**: Local on-device; no data is sent to any external cloud service (except the optional local Ollama LLM)
- **Data types supported**: Numerical (integer/float), Categorical (string), Datetime, and mixed-type columns
- **Output**: Cleaned Parquet files, downloadable CSVs, Quarantine audit logs, visualization charts, LLM insights, and SQL query results
- **Out of scope**: Real-time streaming data ingestion, database connectors, multi-user collaboration (single-session architecture)

---

## 2. Literature Review

### 2.1 Anomaly Detection Methods

**Isolation Forest (Liu et al., 2008)** — The core detection algorithm used in DataSentinel. Isolation Forest operates by randomly partitioning the feature space using decision trees. Anomalous points, being statistically rare and distinct, are isolated in fewer partitions (shorter path lengths) than normal points. It is computationally efficient at O(n log n), works without labeled data (unsupervised), and is robust to high-dimensional datasets. DataSentinel uses 200 estimators with Z-Score thresholding (`mean + 1.5σ`) to calibrate sensitivity.

**HistGradientBoosting Classifier (Chen & Guestrin, 2016 — XGBoost lineage)** — When labeled ground truth exists (e.g., a `Class` or `fraud` column), DataSentinel activates a Tier-2 supervised engine. This gradient-boosted decision tree classifier is trained on the full feature set and produces calibrated probability scores (0–100%) that become the `Threat_Score` field.

**KNN Imputation (Troyanskaya et al., 2001)** — Used in the Contextual Imputation cleaning strategy. K-Nearest Neighbors (k=5, distance-weighted) fills corrupted or anomalous numerical cells by finding the 5 most similar rows in feature space and computing a weighted average of their values for the target column.

**Winsorization (Tukey, 1977)** — A robust outlier capping technique that replaces extreme values above the 95th percentile or below the 5th percentile with the respective boundary values, computed only from the non-anomalous portion of the dataset to prevent pollution.

### 2.2 NLP Anomaly Detection

DataSentinel implements lightweight text feature engineering without requiring a heavy external model. For each string column, the system computes:
- **Character count** (`_length`)
- **Digit ratio** (`_digit_ratio`) — proportion of characters that are numeric
- **Uppercase ratio** (`_upper_ratio`) — flags ALL-CAPS strings
- **Special character ratio** (`_special_ratio`) — detects injection attempts, malformed data

These four features per text column are fed into the Isolation Forest alongside numerical features, enabling the model to flag bot-generated text, SQL injection strings, and typos purely from formatting patterns.

### 2.3 Velocity Analysis

Inspired by fraud detection systems used in banking (e.g., Visa's NeuroFlex), DataSentinel's Velocity Engine computes rolling temporal aggregations to detect unusual transaction bursts:
- **24-hour rolling sum** of financial columns per entity (user/account/merchant)
- **1-hour transaction count** per entity

These provide the model with contextual time-series signals that static approaches miss — for example, a single $50 transaction is normal, but 200 such transactions in one hour is an unambiguous velocity anomaly.

### 2.4 Local LLM Integration

Rather than sending sensitive business data to commercial APIs, DataSentinel integrates with **Ollama** — a framework for running large language models locally. The Phi-3 model is prompted with structured dataset statistics to generate the OIA (Observation-Insight-Action) framework, a reporting standard used in management consulting and business intelligence.

### 2.5 In-Memory SQL with DuckDB

DuckDB is an embedded analytical database that operates directly on Polars DataFrames and Parquet files without requiring a server process. DataSentinel uses DuckDB to execute the SQL generated by the LLM's natural language translation, providing sub-millisecond query performance on multi-hundred-thousand-row datasets entirely in memory.

---

## 3. Proposed System

DataSentinel is a **7-step guided pipeline** presented as a progressive multi-stage web application. Each step builds on the previous, creating a coherent data quality workflow:

```
UPLOAD → DETECT → CLEAN → COMPARE → VISUALIZE → INSIGHTS → QUERY/EXPORT
```

### 3.1 Features and Functionality

#### 3.1.1 Data Quality Contract (Schema Enforcer)
Before any processing begins, uploaded files are validated against a minimum quality contract:
- Rejects completely empty datasets
- Rejects datasets with fewer than 3 columns (insufficient for ML pattern detection)
- Flags columns that are 100% null ("ghost columns")
- Returns descriptive error messages shown in the UI

#### 3.1.2 Multi-Modal Anomaly Detection
The Detection Engine runs three parallel analysis passes:

| Pass | Target | Method |
|------|--------|--------|
| Numerical | All float/integer columns | Isolation Forest (200 trees, Z-Score threshold) |
| Categorical | All string columns | Frequency encoding → Isolation Forest |
| Textual | String columns with text content | NLP feature engineering (4 features per column) |
| Temporal | Datetime + entity columns | Velocity Engine (rolling sums/counts) |
| Supervised | Datasets with `Class`/`fraud` labels | HistGradientBoosting + probability calibration |

Every anomalous row receives:
- A boolean `is_anomaly` flag
- A `Threat_Score` (0–100%) representing AI confidence
- A plain-English `AI_Reason` citing the exact column(s) and values responsible

#### 3.1.3 Threat Score Strictness Slider
The Detection tab provides an interactive slider that dynamically filters visible anomalies by Threat Score threshold. Sliding right increases precision (only high-confidence anomalies); sliding left increases recall (all suspicious rows). This allows analysts to tune the sensitivity without re-running the model.

#### 3.1.4 Five Cleaning Strategies
The Clean tab presents five sanitization methods as interactive flip-cards — each with a technical front face and a plain-English "analogy" back face:

| Strategy | Mechanism | Best For |
|----------|-----------|---------|
| **Quarantine Protocol** | Moves anomalies to a secure audit Parquet file | Financial / forensic data |
| **Smart Winsorization** | Caps extremes to 5th–95th percentile bounds | Large numerical datasets |
| **Categorical Masking** | Replaces anomalous strings with `[REDACTED_ANOMALY]` | Text-heavy / review data |
| **Contextual Imputation** | KNN (k=5) fills corrupted cells from similar rows | Sensor / demographic data |
| **Hard Drop** | Permanently deletes anomalous rows | Strict integrity requirements |

The AI automatically recommends the optimal strategy based on column name heuristics and dataset structure.

#### 3.1.5 Quarantine Vault Audit Log
When Quarantine or Hard Drop is applied, all removed rows are preserved in `quarantined_data.parquet`. The Quarantine Vault modal displays these records with their Threat Scores and AI Reasons, and allows export as a CSV audit trail — satisfying compliance requirements in regulated industries.

#### 3.1.6 Before/After Compare View
After cleaning, the Compare tab renders a structured diff of every row that was modified (for Winsorize, Mask, Impute strategies), showing the original value crossed-out beside the new value with color-coded `red → green` formatting. Engineered columns (velocities, NLP features, frequency encodings) are automatically filtered out so only the user's original columns appear.

#### 3.1.7 Statistical Visualization Suite
The Visualizer tab provides three interactive views:

1. **Global Distribution Curve** — A 50-bin Z-Score histogram comparing the raw dataset distribution (red) against the cleaned distribution (emerald), rendered as an animated bar chart
2. **Pairwise Scatter Explorer** — An SVG scatter plot with a line of best fit and Pearson correlation coefficient (r-value) for any two selected numerical columns
3. **Categorical Frequency Analyser** — Animated horizontal bar charts showing top-N value frequencies for any selected text/categorical column

#### 3.1.8 LLM Insight Engine (OIA Framework)
The Insights tab triggers a call to the local Ollama API. DataSentinel constructs a structured prompt with dataset statistics, anomaly counts, column names, and data types, then asks Phi-3 to respond with a list of OIA (Observation → Insight → Action) structured findings. The component handles arbitrary LLM response formats through fuzzy field extraction and key aliasing (e.g., `recommendation` maps to `action`).

#### 3.1.9 Natural Language Data Co-Pilot
The Query tab provides a chat interface powered by DuckDB where users can:
- **Explore mode**: Ask questions in plain English ("Show me all transactions above $5000") — the backend translates to SQL, executes on the cleaned dataset, and returns tabular results
- **Modify mode**: Issue data transformation commands ("Set all [REDACTED] values in the Name column to Unknown") — the backend generates a SQL `UPDATE` query, presents it for review, then executes only after explicit user confirmation (preventing accidental destructive operations)

#### 3.1.10 AG Grid Review & Export
The final tab renders the cleaned dataset in a fully interactive AG Grid spreadsheet with sorting, filtering, and inline cell editing. Users can make manual corrections directly in the browser before exporting the final CSV via the Download button.

---

## 4. Requirements Analysis

### 4.1 Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-01 | System shall accept CSV file uploads up to at least 150,000 rows |
| FR-02 | System shall validate schema quality before processing |
| FR-03 | System shall detect numerical, categorical, textual, and temporal anomalies |
| FR-04 | System shall assign every row a boolean anomaly flag and numerical Threat Score |
| FR-05 | System shall generate a plain-English reason for each anomaly citing specific columns |
| FR-06 | System shall recommend an optimal cleaning strategy based on dataset domain |
| FR-07 | System shall preserve anomalous rows in a queryable Quarantine audit log |
| FR-08 | System shall provide at least 5 distinct cleaning strategies |
| FR-09 | System shall display statistical distribution charts before and after cleaning |
| FR-10 | System shall generate LLM-powered insights in OIA format |
| FR-11 | System shall execute natural language queries against the cleaned dataset |
| FR-12 | System shall allow user preview and confirmation before destructive SQL edits |
| FR-13 | System shall export the cleaned dataset as a downloadable CSV |
| FR-14 | System shall strip all internal AI metadata columns from exported files |
| FR-15 | System shall automatically clean up sessions older than 24 hours |

### 4.2 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-01 | **Performance** — Detection pipeline execution time | < 30 seconds for 10,000 rows |
| NFR-02 | **Security** — Session ID validation | Strict UUID regex; prevents path traversal |
| NFR-03 | **Security** — CORS policy | Environment-variable whitelist; no wildcard |
| NFR-04 | **Privacy** — Data residency | All data processed on-device; no cloud egress |
| NFR-05 | **Reliability** — CSV parsing | Dual-engine fallback (Polars → Pandas) |
| NFR-06 | **Usability** — Error messages | Plain-English descriptions with actionable guidance |
| NFR-07 | **Maintainability** — Code architecture | Modular `engines/` package; <200 lines per module |
| NFR-08 | **Type Safety** — Frontend | TypeScript strict mode; zero `any` types |

### 4.3 Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16 GB (for Ollama) |
| Storage | 2 GB free | 10 GB (Llama 3 and Phi-3 models ~7 GB) |
| OS | Windows 10 / macOS 12 / Ubuntu 20.04 | Windows 11 / macOS 14 |
| Python | 3.10+ | 3.11+ |
| Node.js | 18+ | 20+ (LTS) |

---

## 5. Project Design

### 5.1 Use Case Diagram

**Primary Actor: Data Analyst**

```
Data Analyst
    │
    ├──[Upload CSV Dataset]
    │       └── includes [Schema Validation]
    │
    ├──[View Anomaly Report]
    │       ├── includes [Apply Threat Score Filter]
    │       └── includes [Read AI Explanation]
    │
    ├──[Apply Cleaning Strategy]
    │       ├── extends [Quarantine]
    │       ├── extends [Winsorize]
    │       ├── extends [Mask]
    │       ├── extends [Impute]
    │       └── extends [Drop]
    │
    ├──[View Quarantine Vault]
    │       └── includes [Export Audit CSV]
    │
    ├──[View Statistical Visualizations]
    │       ├── extends [Distribution Curve]
    │       ├── extends [Pairwise Scatter]
    │       └── extends [Categorical Frequency]
    │
    ├──[Generate AI Insights]
    │       └── uses [Ollama Local LLM]
    │
    ├──[Query Dataset (Natural Language)]
    │       └── uses [DuckDB SQL Engine]
    │
    └──[Export Cleaned Dataset]
```

### 5.2 Data Flow Diagram (DFD)

**Level 0 — Context Diagram:**

```
[User] ──CSV Upload──▶ [DataSentinel System] ──Cleaned CSV──▶ [User]
                               │
                       ──Insights──▶ [User]
                       ──Query Results──▶ [User]
```

**Level 1 — System DFD:**

```
[User]
   │
   │ CSV File
   ▼
[1.0 Schema Validation]
   │ Validated DataFrame
   ▼
[2.0 Feature Engineering]
   │ NLP Features │ Velocity Features │ Freq Encodings
   ▼
[3.0 Isolation Forest Detection]
   │ is_anomaly, Threat_Score
   ▼
[4.0 AI Reason Generation]
   │ AI_Reason per row
   ▼
[5.0 Session Storage (Parquet)] ◀──────────────────────────┐
   │                                                        │
   ├──API Request──▶ [6.0 Cleaning Engine] ──────────────▶ │
   ├──API Request──▶ [7.0 Visualization Engine]            │
   ├──API Request──▶ [8.0 Insights Engine (Ollama)]        │
   └──API Request──▶ [9.0 Query Engine (DuckDB)] ──────────┘
```

### 5.3 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        NEXT.JS 15 FRONTEND                              │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │page.tsx  │  │Detection  │  │ Clean    │  │Visualizer│  │ Query  │  │
│  │(Upload + │  │.tsx       │  │.tsx +    │  │.tsx      │  │.tsx    │  │
│  │Orchestr.)│  │           │  │Compare   │  │          │  │(Co-Pilot│ │
│  └────┬─────┘  └─────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘  │
│       └──────────────┴──────────────┴──────────────┴────────────┘       │
│                              lib/api.ts (Axios · NEXT_PUBLIC_API_URL)    │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ HTTP REST
┌──────────────────────────────────▼──────────────────────────────────────┐
│                        FASTAPI BACKEND (Port 8000)                      │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐ │
│  │  Route Layer    │    │  utils.py        │    │  schema.py          │ │
│  │  main.py        │    │  · UUID Validate │    │  · SchemaEnforcer   │ │
│  │  · /api/upload/ │    │  · Session Dirs  │    │  · Quality Contract │ │
│  │  · /api/data/   │    │  · Stale Cleanup │    └─────────────────────┘ │
│  │  · /api/clean/  │    │  · Logger        │                            │
│  │  · /api/viz/    │    └──────────────────┘                            │
│  │  · /api/insights│                                                     │
│  │  · /api/query/  │                                                     │
│  └────────┬────────┘                                                     │
│           │                                                              │
│  ┌────────▼───────────────────────────────────────────────────────────┐  │
│  │                      engines/ PACKAGE                              │  │
│  │  ┌────────────┐ ┌───────────┐ ┌──────────┐ ┌────────┐ ┌────────┐  │  │
│  │  │detection.py│ │cleaning.py│ │visualiz. │ │insight │ │query.py│  │  │
│  │  │IsoForest   │ │5 Strats   │ │Statistics│ │OIA+LLM │ │NL→SQL  │  │  │
│  │  │HistGB      │ │KNNImpute  │ │Histogram │ │Ollama  │ │DuckDB  │  │  │
│  │  │Velocity Eng│ │Winsorize  │ │Scatter   │ │Bridge  │ │Confirm │  │  │
│  │  │NLP Features│ │Quarantine │ │Categorical         │ │Execute │  │  │
│  │  └────────────┘ └───────────┘ └──────────┘ └────────┘ └────────┘  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
  ┌───────────────┐     ┌──────────────────┐    ┌─────────────────────┐
  │ Ollama (Local)│     │  DuckDB          │    │ sessions/{uuid}/    │
  │ Llama 3 / Phi-3│     │  In-Memory SQL   │    │ raw_data.parquet    │
  │ LLM Insights  │     │  Analytical DB   │    │ cleaned_data.parquet│
  └───────────────┘     └──────────────────┘    │ quarantined.parquet │
                                                 └─────────────────────┘
```

### 5.4 Implementation

The implementation follows a **service-oriented backend** architecture with a **component-driven frontend**:

**Backend Implementation Sequence:**
1. FastAPI app bootstraps with CORS middleware from `CORS_ORIGINS` environment variable
2. Upload request triggers `SchemaEnforcer.validate()` — rejects bad data before any ML computation
3. Valid DataFrame passed to `process_and_detect()` in `engines/detection.py`
4. Detection engine: deduplication → Velocity Engine → NLP feature extraction → Isolation Forest → Threat Scoring → AI Reason generation → write `raw_data.parquet`
5. Cleaning request dispatches to `engines/cleaning.py` with the chosen strategy → strips engineered columns → writes `cleaned_data.parquet`
6. Visualization, Insights, Query endpoints serve the respective engine outputs
7. `validate_session_id()` guards every endpoint — rejects non-UUID paths

**Frontend Implementation Sequence:**
1. `page.tsx` manages global state: `sessionId`, `currentStep`, `cachedInsights`
2. File upload → `api.post('/api/upload/')` → sets session ID
3. Step progression unlocks each tab component
4. All API calls flow through `lib/api.ts` (single Axios instance with `NEXT_PUBLIC_API_URL` base)
5. TypeScript interfaces in `types/api.ts` enforce strict request/response shapes

---

## 6. Technical Specification

### 6.1 Backend Technology Stack

| Technology | Version | Role |
|------------|---------|------|
| **Python** | 3.11+ | Runtime language |
| **FastAPI** | 0.115+ | REST API framework; async-capable, auto OpenAPI docs |
| **Uvicorn** | latest | ASGI server with hot-reload in development |
| **Polars** | latest | Primary DataFrame engine; Rust-based, 10-100× faster than Pandas |
| **Pandas** | 2.x | Fallback CSV parser; Scikit-learn bridge |
| **NumPy** | 1.26+ | Numerical operations for scoring and vectorization |
| **Scikit-learn** | 1.5+ | Isolation Forest, HistGradientBoosting, KNNImputer |
| **DuckDB** | latest | In-memory analytical SQL engine for Query Co-Pilot |
| **Ollama** | latest | Local LLM runner for Llama 3 (Query) and Phi-3 (Insights) |
| **python-multipart** | latest | Multipart form handling for file upload |
| **Parquet (via Polars)** | — | Columnar binary storage format for sessions |

### 6.2 Frontend Technology Stack

| Technology | Version | Role |
|------------|---------|------|
| **Next.js** | 15 (App Router) | Full-stack React framework |
| **React** | 19 | UI component library |
| **TypeScript** | 5.x (strict mode) | Type-safe component development |
| **Tailwind CSS** | v4 | Utility-first styling |
| **Axios** | latest | HTTP client (centralized in `lib/api.ts`) |
| **Framer Motion** | latest | Animation library for transitions and micro-interactions |
| **AG Grid Community** | latest | Enterprise-grade data grid for Review & Export tab |
| **Lucide React** | latest | Icon library |

### 6.3 Key Algorithms

#### Isolation Forest Configuration
```
n_estimators  = 200      # Tree count (higher = more stable, slower)
random_state  = 42       # Reproducibility
threshold     = μ + 1.5σ # Z-Score calibration of anomaly scores
contamination = auto     # 1.5σ determines the boundary dynamically
```

#### Velocity Engine Window Configuration
```
24h_rolling_sum  → financial column sum per entity per 24-hour window
1h_txn_count     → transaction count per entity per 1-hour window
Anomaly signal   → value > μ + 2.5σ of the respective velocity feature
```

#### Threat Score Computation

*Supervised (Class label available):*
```
Threat_Score = P(class=1 | features) × 100
```
via `HistGradientBoostingClassifier.predict_proba()`

*Unsupervised (synthetic):*
```
For anomalies:  Score = 60 + ((s - threshold) / (max_s - threshold)) × 40
For normals:    Score = ((s - min_s) / (threshold - min_s)) × 40
Output: clamped to [0, 100]
```

### 6.4 API Specification

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/` | GET | Health check | None |
| `/api/upload/` | POST | Upload CSV, run detection pipeline, return session | None |
| `/api/data/{session_id}` | GET | Fetch rows (`is_cleaned`, `only_anomalies` params) | UUID validation |
| `/api/clean/{session_id}` | POST | Apply cleaning strategy (`action` param) | UUID validation |
| `/api/compare/{session_id}` | GET | Get before/after diff of modified rows | UUID validation |
| `/api/viz/{session_id}` | GET | Get visualization data (histograms, scatter, categorical) | UUID validation |
| `/api/insights/{session_id}` | GET | Generate LLM-powered OIA insights | UUID validation |
| `/api/query/{session_id}` | POST | NL → SQL query on cleaned dataset | UUID validation |
| `/api/confirm-edit/{session_id}` | POST | Execute approved destructive SQL edit | UUID validation |
| `/api/download/{session_id}` | GET | Download cleaned or quarantine CSV | UUID validation |
| `/api/quarantine/{session_id}` | GET | Fetch quarantine vault records | UUID validation |

### 6.5 Session Architecture

Each uploaded dataset is assigned a `UUID v4` session identifier. All processed data is stored under:

```
backend/
  sessions/
    {uuid-v4}/
      raw_data.parquet         ← Original CSV + is_anomaly + Threat_Score + AI_Reason
      cleaned_data.parquet     ← Post-cleaning dataset (engineered columns stripped)
      quarantined_data.parquet ← Anomalous rows preserved as audit log (optional)
```

Sessions are purged automatically by `cleanup_stale_sessions(max_age_hours=24)`, which runs on every upload request.

### 6.6 Security Measures

| Threat | Mitigation |
|--------|-----------|
| **Path Traversal** | All session IDs validated against strict UUID regex before filesystem access |
| **CORS Abuse** | Origins restricted to `CORS_ORIGINS` env var whitelist (no wildcard `*`) |
| **Destructive SQL** | Edit queries shown to user for confirmation before execution; DuckDB sandboxed to session |
| **Large File DoS** | FastAPI streaming upload; Polars lazy evaluation limits memory spikes |
| **Data Exfiltration** | All processing on-device; Ollama runs locally; no external API calls with user data |
| **Ghost Column Attack** | SchemaEnforcer rejects datasets with 100%-null columns |

---

## 7. Project Scheduling

### 7.1 Development Timeline

| Phase | Tasks | Duration |
|-------|-------|---------|
| **Phase 1 — Research & Design** | Technology selection, algorithm research, UI wireframes | Week 1 |
| **Phase 2 — Backend Core** | FastAPI setup, Isolation Forest pipeline, CSV upload/storage | Week 2 |
| **Phase 3 — Frontend Scaffold** | Next.js setup, component structure, API client | Week 2–3 |
| **Phase 4 — Feature Expansion** | Velocity Engine, NLP features, Supervised Threat Scoring | Week 3 |
| **Phase 5 — Cleaning Strategies** | All 5 cleaning methods, Quarantine Vault, Compare view | Week 4 |
| **Phase 6 — Intelligence Layer** | Ollama integration, DuckDB query engine, OIA insights | Week 4–5 |
| **Phase 7 — Visualization Suite** | Distribution charts, Pairwise scatter, Categorical frequency | Week 5 |
| **Phase 8 — Architecture Refactor** | Modular engines/ package, security hardening, type safety | Week 6 |
| **Phase 9 — QA & Polish** | Bug fixes, performance testing, final UI polish | Week 6 |

### 7.2 Milestones

| Milestone | Deliverable |
|-----------|-------------|
| M1 | Working anomaly detection pipeline with basic UI |
| M2 | Complete cleaning workflow with 5 strategies |
| M3 | Visualization suite operational |
| M4 | LLM insights and SQL co-pilot functional |
| M5 | Full architecture refactor, security audit complete |
| M6 | Final build submitted and pushed to GitHub |

---

## 8. Results

### 8.1 Detection Accuracy

On the included test datasets:

| Dataset | Rows | Anomalies Detected | Precision | Notes |
|---------|------|--------------------|-----------|-------|
| `creditcard.csv` | 284,807 | ~492 | High (with Class label) | Supervised HistGB mode activated |
| `Titanic-Dataset.csv` | 891 | ~47 | Moderate | Mixed numeric + categorical |
| `amazon.csv` | ~34,000 | ~1,200 | High | NLP feature detection dominant |
| `bad_data.csv` | 12 | 4 | Exact | Edge case validation |
| `velocity_engine.csv` | 50 | 8 | High | Velocity feature dominant |

### 8.2 Performance Benchmarks

| Operation | Dataset Size | Time (approx.) |
|-----------|-------------|----------------|
| Upload + Detection | 1,000 rows | ~2 seconds |
| Upload + Detection | 10,000 rows | ~12 seconds |
| Upload + Detection | 100,000 rows | ~85 seconds |
| KNN Imputation | 10,000 rows | ~8 seconds |
| Visualization data | Any | < 1 second |
| DuckDB query | 100,000 rows | < 200ms |

### 8.3 Key Achievements

- **Zero false API leaks**: Strict TypeScript interfaces enforce all request/response shapes; build fails on type errors
- **Zero CORS wildcards**: Environment-based origin whitelist deployed
- **100% session safety**: UUID validation prevents all path traversal attacks
- **Auditability**: Quarantine Vault preserves all removed records with Threat Score and AI Reason
- **Explainability**: Plain-English reasons cite exact column names and statistical deviations

---

## 9. Conclusion

DataSentinel successfully demonstrates that enterprise-grade data quality assurance does not require expensive commercial tools, cloud subscriptions, or deep technical expertise. By combining classical statistical methods (Isolation Forest, Winsorization), modern supervised learning (HistGradientBoosting, KNN Imputation), time-series velocity analysis, NLP-based text anomaly detection, and local LLM inference — all orchestrated through a clean REST API and delivered via a premium web interface — the platform provides a complete end-to-end data quality pipeline in a single local application.

The architecture refactor completed during late development — decomposing the 1,027-line monolith into a 7-module `engines/` package with strict security controls, centralized API configuration, and full TypeScript type safety — demonstrates production-engineering principles alongside the research contributions.

DataSentinel is not merely a proof of concept; it is a functional product that can be immediately applied to real-world data quality problems in finance, healthcare, IoT, and e-commerce domains.

---

## 10. Future Scope

| Feature | Description | Priority |
|---------|-------------|---------|
| **Automated Test Suite** | `pytest` for all engine modules; React Testing Library for frontend components | HIGH |
| **Real-Time Streaming** | WebSocket endpoint for incremental anomaly detection on data streams | MEDIUM |
| **Database Connectors** | Direct connection to PostgreSQL, MySQL, BigQuery, Snowflake instead of CSV upload | MEDIUM |
| **Multi-Dataset Comparison** | Compare quality metrics across multiple uploads in a single session | MEDIUM |
| **Custom Rules Engine** | User-defined column-specific thresholds and validation rules (beyond the ML model) | MEDIUM |
| **Scheduled Scans** | Cron-based recurring quality checks on connected data sources | LOW |
| **Multi-User Collaboration** | Named sessions, shared audit reports, team workspaces | LOW |
| **Cloud Deployment** | Docker-compose for production, Kubernetes for scale | LOW |
| **GDPR Compliance Module** | PII detection and auto-redaction of personal data fields | HIGH |
| **Git LFS for Large Test Data** | Replace local CSV files with Git Large File Storage links | LOW |

---

## References

1. Liu, F. T., Ting, K. M., & Zhou, Z. H. (2008). *Isolation Forest*. IEEE International Conference on Data Mining.

2. Chen, T., & Guestrin, C. (2016). *XGBoost: A Scalable Tree Boosting System*. ACM SIGKDD International Conference on Knowledge Discovery and Data Mining.

3. Troyanskaya, O., et al. (2001). *Missing value estimation methods for DNA microarrays*. Bioinformatics, 17(6), 520–525. (KNN Imputation)

4. Tukey, J. W. (1977). *Exploratory Data Analysis*. Addison-Wesley. (Winsorization)

5. FastAPI Documentation — https://fastapi.tiangolo.com

6. Polars Documentation — https://pola.rs

7. Ollama Project — https://ollama.com

8. DuckDB Documentation — https://duckdb.org

9. Next.js 15 Documentation — https://nextjs.org/docs

10. Scikit-learn: Machine Learning in Python — Pedregosa et al., JMLR 12, pp. 2825–2830, 2011.

---

*DataSentinel — AI-Powered Data Quality Intelligence Platform*
*GitHub: https://github.com/GhoshChinmay/DataSentinel*
