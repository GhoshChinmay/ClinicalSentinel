<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Next.js-16-000000?style=for-the-badge&logo=next.js&logoColor=white" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Groq_LPU-Llama_3.3_70B-FF6B35?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Polars-1.27-CD792C?style=for-the-badge" />
  <img src="https://img.shields.io/badge/DuckDB-1.2-FFF000?style=for-the-badge&logo=duckdb&logoColor=black" />
  <img src="https://img.shields.io/badge/Three.js-0.183-000000?style=for-the-badge&logo=three.js&logoColor=white" />
</p>

<h1 align="center">🛡️ DataSentinel</h1>

<p align="center">
  <strong>AI-Powered Autonomous Data Quality & Anomaly Detection Platform</strong><br/>
  A multi-agent, neuro-symbolic system that ingests any dataset, detects anomalies, vaults PII,<br/>
  cleans data intelligently, and lets you query it using natural language — all in one cinematic pipeline.
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-features">Features</a> •
  <a href="#%EF%B8%8F-system-architecture">Architecture</a> •
  <a href="#-data-pipeline-flow">Pipeline</a> •
  <a href="#-project-structure">Structure</a> •
  <a href="#-api-reference">API Reference</a> •
  <a href="#-tech-stack">Tech Stack</a> •
  <a href="#-security-model">Security</a> •
  <a href="#-environment-variables">Environment</a>
</p>

---

## ✨ Features

| Category | Feature | Description |
|----------|---------|-------------|
| 🔍 **Detection** | Isolation Forest + SHAP | Statistical anomaly detection with per-row AI explainability and threat scoring |
| 🧠 **Neuro-Symbolic AI** | Logic Gate Engine | Groq LLM generates domain-specific mathematical validation rules (e.g., `age > 0`, `salary < revenue`) that are compiled into Polars expressions |
| 🛡️ **Privacy** | PII Scanner & Vault | Local-edge regex + heuristic PII detection with GDPR-compliant SHA-256 pseudonymisation — sensitive data never leaves the machine |
| ⚡ **LLM Acceleration** | Groq LPU (Llama 3.3 70B) | Millisecond-latency AI inference for SQL generation, narrative insights, and rule synthesis |
| 💬 **Natural Language Query** | Agentic RAG Chat | Ask questions in plain English — the agent generates SQL, executes it via DuckDB, and self-heals on errors with a retry loop |
| 🧹 **Smart Cleaning** | Multi-Strategy Engine | Drop, quarantine, winsorize, mask, or KNN-impute anomalies with before/after dataset comparison |
| 📊 **Visual Analytics** | Interactive Dashboards | Correlation heatmaps, distribution histograms, scatter plots, and categorical breakdowns powered by Recharts |
| 📋 **Quality Reports** | Exportable Scorecards | AI-generated data quality reports with health scores, missing data maps, and column profiling |
| 🔌 **Live DB Connect** | PostgreSQL Bridge | Connect to production databases for real-time querying without data movement |
| 📚 **Teachable AI** | Business Dictionary | Teach the agent domain-specific business terms and SQL logic that persist across sessions |
| 🔒 **Audit Trail** | SOC2-Ready Logging | Immutable JSONL audit trail of every AI-driven data mutation for compliance |
| 🎬 **Cinematic UI** | Premium Experience | GSAP scroll-driven animations, Three.js particle simulations (PurificationCore & NeuralCore), Lenis smooth scrolling |

---

## 🚀 Quick Start

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.11+ | Backend runtime |
| **Node.js** | 18+ | Frontend runtime |
| **npm** | 9+ | Package management |
| **Groq API Key** | — | LLM inference ([Get one free →](https://console.groq.com)) |

### 1. Clone the Repository

```bash
git clone https://github.com/GhoshChinmay/DataSentinel.git
cd DataSentinel
```

### 2. Backend Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file inside the `backend/` directory:

```env
# ━━━ REQUIRED ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GROQ_API_KEY=gsk_your_key_here

# ━━━ OPTIONAL ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Protect API endpoints with a key (enables auth guard)
# DS_API_KEY=your_secure_api_key

# Custom salt for PII pseudonymisation (defaults to built-in)
# DS_PII_SALT=your_custom_salt

# CORS whitelist (defaults to localhost:3000)
# CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### 4. Start the Backend

```bash
uvicorn main:app --reload
```

The API server starts at **http://localhost:8000**:

| URL | Description |
|-----|-------------|
| `http://localhost:8000/` | Health check — `{"status": "DataSentinel detection engine is online."}` |
| `http://localhost:8000/docs` | Interactive Swagger API documentation |
| `http://localhost:8000/redoc` | ReDoc API documentation |

### 5. Frontend Setup

Open a **new terminal**:

```bash
cd frontend

# Install dependencies
npm install
```

### 6. Start the Frontend

```bash
npm run dev
```

The application opens at **http://localhost:3000**.

---

## 🏗️ System Architecture

<p align="center">
  <img src="frontend/public/architecture.png" alt="DataSentinel System Architecture" width="100%" />
</p>

### Architecture Overview

DataSentinel uses a **decoupled client-server architecture** with a multi-engine backend design:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     BROWSER — Next.js 16 + React 19                     │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│  │ 3D Landing │ │Detection │ │ Insights │ │ Cleaning │ │ NL Query   │  │
│  │ Three.js   │ │Dashboard │ │  Panel   │ │ Compare  │ │ (SSE Chat) │  │
│  └────────────┘ └──────────┘ └──────────┘ └──────────┘ └────────────┘  │
│                     Axios API Service + Auth Interceptor                 │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ REST API / Server-Sent Events (SSE)
┌──────────────────────────────▼──────────────────────────────────────────┐
│                    FastAPI Backend (Python 3.11+)                        │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  API Gateway: Rate Limiting (SlowAPI) · Auth Guard · CORS · Validation  │
│  └──────┬─────┬──────┬──────┬──────┬──────┬──────┬──────┬────────────┘ │
│         │     │      │      │      │      │      │      │              │
│    ┌────▼──┐┌─▼───┐┌─▼───┐┌─▼───┐┌─▼───┐┌─▼───┐┌─▼───┐┌─▼────────┐   │
│    │ PII   ││Detec││Logic││ NLP ││Clean││Query││Insig││Visualiz- │   │
│    │Scanner││tion ││Gate ││Bridg││  -  ││  -  ││hts  ││ation     │   │
│    │Regex+ ││IFore││Neuro││TF-ID││Polar││Duck ││Stats││Engine    │   │
│    │SHA256 ││st+  ││Symbo││F+SVD││s    ││DB+  ││+LLM ││          │   │
│    │       ││SHAP ││lic  ││     ││     ││Groq ││     ││          │   │
│    └───────┘└─────┘└─────┘└─────┘└─────┘└──┬──┘└──┬──┘└──────────┘   │
│                                             │      │                   │
│  ┌──────────────────────────────────────────▼──────▼─────────────────┐ │
│  │  Groq Client: Centralized LLM wrapper with retry + error handling │ │
│  │  Schema Enforcer: Data contract validation on upload              │ │
│  │  Business Dictionary: Persistent RAG knowledge base (JSON)        │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  ┌────────────────────────────┐  ┌─────────────────────────────────┐   │
│  │ 💾 Session Storage         │  │ 📝 Audit Trail                  │   │
│  │ Parquet files in           │  │ Immutable JSONL logs in         │   │
│  │ sessions/{uuid}/           │  │ logs/audit_trail.jsonl          │   │
│  └────────────────────────────┘  └─────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
                               │
                    ┌──────────▼───────────┐
                    │   ☁️  Groq Cloud LPU  │
                    │   Llama 3.3 70B      │
                    │   (AI Inference)      │
                    └──────────────────────┘
```

---

## 🔄 Data Pipeline Flow

The platform processes data through a **7-stage sequential pipeline**:

```
 ┌──────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────┐
 │ 1. UPLOAD│───▶│2. PII    │───▶│3. ANOMALY    │───▶│4. AI     │
 │ CSV/JSON/│    │  VAULT   │    │  DETECTION   │    │ INSIGHTS │
 │ Excel    │    │  SHA-256 │    │  IForest+SHAP│    │ Stats+LLM│
 └──────────┘    └──────────┘    └──────────────┘    └──────────┘
                                                          │
 ┌──────────┐    ┌──────────┐    ┌──────────────┐         │
 │7. EXPORT │◀───│6. QUERY  │◀───│5. SMART      │◀────────┘
 │ Report + │    │  & EXPLORE│    │  CLEANING    │
 │ Download │    │  NL → SQL │    │  Drop/Quarant│
 └──────────┘    └──────────┘    └──────────────┘
```

| Stage | Engine | What Happens |
|-------|--------|--------------|
| **1. Upload** | `main.py` + `schema.py` | File parsed (CSV/JSON/Excel) → Schema contract validation → Parquet storage |
| **2. PII Vault** | `pii_scanner.py` | Regex + heuristic scan for emails, phones, SSNs → Optional SHA-256 pseudonymisation |
| **3. Detection** | `detection.py` + `logic_gate.py` + `nlp_bridge.py` | NLP feature engineering → Neuro-symbolic rule generation → Isolation Forest → SHAP explainability → Threat scoring |
| **4. AI Insights** | `insights.py` + `groq_client.py` | Statistical profiling (null rates, skewness, correlations) → Groq LLM narrative generation |
| **5. Cleaning** | `cleaning.py` | Drop, quarantine, winsorize, mask, or KNN-impute anomalies → Save cleaned Parquet |
| **6. Query** | `query.py` + DuckDB | Natural language → Groq generates SQL → DuckDB executes → Auto-correction retry loop |
| **7. Export** | `quality.py` + `visualization.py` | Quality report generation → Chart data aggregation → CSV download |

---

## 📁 Project Structure

```
DataSentinel/
├── backend/
│   ├── main.py                  # FastAPI application & all route definitions
│   ├── auth.py                  # API key authentication guard (constant-time comparison)
│   ├── schema.py                # Data contract validation (SchemaEnforcer)
│   ├── utils.py                 # Session management, logging, audit trail utilities
│   ├── groq_client.py           # Centralized Groq LLM client with retry logic
│   ├── stress_test.py           # End-to-end stress test utility
│   ├── engines/
│   │   ├── __init__.py          # Re-exports all engine functions
│   │   ├── detection.py         # Isolation Forest + SHAP anomaly detection pipeline
│   │   ├── cleaning.py          # Multi-strategy anomaly cleaning (drop/quarantine/impute)
│   │   ├── insights.py          # Statistical profiling + AI narrative generation
│   │   ├── query.py             # Natural language → SQL via Groq + DuckDB execution
│   │   ├── visualization.py     # Chart data aggregation (histograms, correlations)
│   │   ├── quality.py           # Data quality report & health score generation
│   │   ├── logic_gate.py        # AI-generated neuro-symbolic validation rules
│   │   ├── nlp_bridge.py        # NLP feature engineering (TF-IDF + SVD) for text columns
│   │   └── pii_scanner.py       # PII detection & SHA-256 pseudonymisation
│   ├── data/
│   │   ├── fraud_transactions.csv    # Sample: Financial fraud dataset
│   │   ├── patient_vitals.csv        # Sample: Healthcare vitals dataset
│   │   ├── ecommerce_reviews.csv     # Sample: E-commerce reviews dataset
│   │   ├── business_dictionary.json  # Persistent RAG knowledge base
│   │   └── schemas/                  # Data contract schema definitions
│   ├── tests/
│   │   ├── conftest.py          # Pytest fixtures & shared test setup
│   │   ├── test_api.py          # API endpoint integration tests
│   │   ├── test_cleaning.py     # Cleaning engine unit tests
│   │   ├── test_detection.py    # Detection engine unit tests
│   │   ├── test_insights.py     # Insights engine unit tests
│   │   ├── test_query.py        # Query engine unit tests
│   │   └── test_schema.py       # Schema enforcer unit tests
│   ├── requirements.txt         # Python dependencies
│   └── .env                     # Environment variables (not committed)
│
├── frontend/
│   ├── public/
│   │   └── architecture.png     # System architecture diagram
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx         # Main application page & pipeline orchestrator
│   │   │   ├── layout.tsx       # Root layout with SmoothScroller
│   │   │   └── globals.css      # Global styles & Tailwind configuration
│   │   ├── components/
│   │   │   ├── landing/
│   │   │   │   ├── HeroLanding.tsx        # GSAP scroll-driven cinematic intro
│   │   │   │   ├── PurificationCore.tsx   # Three.js data purification particle animation
│   │   │   │   ├── NeuralCore.tsx         # Three.js neural network background
│   │   │   │   └── AmbientAurora.tsx      # CSS ambient aurora backdrop
│   │   │   ├── detection/       # Anomaly detection results with SHAP visualizations
│   │   │   ├── insights/        # AI-generated insights dashboard with profiles
│   │   │   ├── clean/           # Multi-strategy cleaning action panel
│   │   │   ├── compare/         # Before/after dataset diff comparison
│   │   │   ├── review-edit/     # Data review & inline edit interface
│   │   │   ├── visualizer/      # Charts (histograms, heatmaps, scatter plots)
│   │   │   ├── query/           # Natural language query chat interface (SSE)
│   │   │   ├── export-report/   # Quality report export panel
│   │   │   ├── pii-modal/       # PII detection & pseudonymisation modal
│   │   │   └── SmoothScroller.tsx  # Lenis smooth scroll wrapper
│   │   ├── hooks/
│   │   │   ├── use-detection.ts # Anomaly data fetching & feedback state
│   │   │   ├── use-compare.ts   # Before/after comparison data hook
│   │   │   └── use-viz.ts       # Visualization data & tab state hook
│   │   ├── services/
│   │   │   └── api.service.ts   # Axios instance with auth interceptor
│   │   ├── types/
│   │   │   └── api.ts           # Shared TypeScript interfaces (zero `any` types)
│   │   └── constants/
│   │       └── config.ts        # API base URL & key configuration
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   ├── eslint.config.mjs
│   └── postcss.config.mjs
│
├── .gitignore
└── README.md
```

---

## 📡 API Reference

All endpoints are served at `http://localhost:8000`. Interactive Swagger docs at `/docs`.

### Core Data Pipeline

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check — returns engine status |
| `GET` | `/api/health` | Verify Groq API connectivity & model availability |
| `POST` | `/api/upload/` | Upload a dataset (CSV, JSON, Excel, Parquet) with schema validation |
| `GET` | `/api/data/{session_id}` | Fetch dataset rows with filtering (`is_cleaned`, `only_anomalies`) |
| `POST` | `/api/clean/{session_id}` | Clean anomalies — actions: `drop`, `quarantine`, `winsorize`, `mask`, `impute` |
| `GET` | `/api/compare/{session_id}` | Compare raw vs cleaned data side-by-side |
| `GET` | `/api/viz/{session_id}` | Get visualization aggregations (histograms, correlations, categorical) |
| `GET` | `/api/insights/{session_id}` | Generate AI insights with statistical profiles & LLM narratives |
| `GET` | `/api/report/{session_id}` | Generate exportable quality report with health score |
| `GET` | `/api/download/{session_id}` | Download cleaned dataset as CSV |

### Agentic Query System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/query/{session_id}` | Natural language query — streams results via SSE (modes: `explore` / `edit`) |
| `POST` | `/api/confirm-edit/{session_id}` | Execute a confirmed SQL mutation with audit logging |

### Privacy & Security

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/pii-scan/{session_id}` | Scan uploaded data for PII (emails, phones, SSNs, addresses) |
| `POST` | `/api/pseudonymise/{session_id}` | SHA-256 pseudonymise selected PII columns |
| `GET` | `/api/quarantine/{session_id}` | View quarantined anomaly rows |
| `POST` | `/api/feedback/` | Submit human feedback on anomaly classifications |

### Knowledge & Administration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/knowledge/learn` | Teach the AI a business term with SQL logic & keywords |
| `POST` | `/api/connect-db/{session_id}` | Connect a live PostgreSQL database for real-time querying |
| `GET` | `/api/admin/audit-logs` | Fetch the immutable audit trail of all AI data mutations |

### Sample Datasets

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/samples` | List available built-in sample datasets |
| `POST` | `/api/load-sample/{filename}` | Load a sample dataset through the full detection pipeline |

---

## 🔧 Tech Stack

### Backend

| Package | Version | Purpose |
|---------|---------|---------|
| **FastAPI** | 0.115 | Async REST API framework with auto-generated docs |
| **Polars** | 1.27 | High-performance DataFrame engine (10-100x faster than Pandas) |
| **scikit-learn** | 1.6 | Isolation Forest anomaly detection algorithm |
| **SHAP** | 0.46 | Model-agnostic explainability (per-row feature attribution) |
| **DuckDB** | 1.2 | In-process analytical SQL engine for natural language queries |
| **Groq SDK** | latest | LLM inference client (Llama 3.3 70B on Groq LPU hardware) |
| **SlowAPI** | 0.1.9 | Rate limiting middleware for API protection |
| **Pandas** | 2.2 | Excel/fallback CSV parsing & compatibility layer |

### Frontend

| Package | Version | Purpose |
|---------|---------|---------|
| **Next.js** | 16 | React framework with App Router & SSR |
| **React** | 19 | UI component library |
| **Three.js** | 0.183 | 3D particle visualization (PurificationCore, NeuralCore) |
| **@react-three/fiber** | 9.6 | React renderer for Three.js scenes |
| **GSAP** | 3.15 | Scroll-driven cinematic animations |
| **Lenis** | 1.3 | Butter-smooth scroll engine |
| **Framer Motion** | 12 | Page transitions & micro-animations |
| **Recharts** | 3.8 | Data visualization charts (bar, scatter, heatmap) |
| **Tailwind CSS** | 4 | Utility-first CSS framework |
| **Axios** | 1.14 | HTTP client with interceptors |

---

## 🔐 Security Model

DataSentinel implements a **defense-in-depth** security architecture:

| Layer | Implementation |
|-------|---------------|
| **API Authentication** | Optional API key guard with constant-time comparison (`DS_API_KEY`) |
| **PII Protection** | Local-edge scanning — PII is detected and vaulted before any data reaches the LLM |
| **Pseudonymisation** | Salted SHA-256 hashing preserves data relationships while protecting identities |
| **Path Traversal Prevention** | UUID-based session isolation — all file paths are validated against session boundaries |
| **SQL Injection Protection** | DuckDB read-only mode for explore queries, whitelist-based mutation validation |
| **File Upload Safety** | File size caps (50MB), extension whitelist, MIME type validation |
| **Rate Limiting** | SlowAPI middleware prevents abuse (configurable per-endpoint limits) |
| **Audit Trail** | Immutable JSONL log of every data mutation for SOC2/compliance readiness |
| **CORS** | Configurable origin whitelist (defaults to `localhost:3000`) |

> **Opt-in Auth Model:** If `DS_API_KEY` is not set, authentication is bypassed for frictionless local development. Set the key in production to enable the auth guard.

---

## 🔑 Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | ✅ **Yes** | — | Your Groq Cloud API key ([get one free](https://console.groq.com)) |
| `DS_API_KEY` | No | — | API key to protect endpoints. Enables auth guard when set |
| `DS_PII_SALT` | No | Built-in default | Cryptographic salt for PII SHA-256 hashing |
| `CORS_ORIGINS` | No | `http://localhost:3000` | Comma-separated allowed CORS origins |

### Frontend (`frontend/.env.local`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | No | `http://127.0.0.1:8000` | Backend API base URL |
| `NEXT_PUBLIC_API_KEY` | No | — | Must match `DS_API_KEY` if auth is enabled on backend |

---

## 🧪 Running Tests

### Backend

```bash
cd backend
source venv/bin/activate   # or venv\Scripts\activate on Windows
pytest -v
```

### Frontend

```bash
cd frontend

# TypeScript type checking (zero errors expected)
npx tsc --noEmit

# ESLint linting (zero errors expected)
npx eslint src/
```

### Stress Test

Run the end-to-end stress test against a running backend:

```bash
cd backend
python stress_test.py
# Generates: stress_test_report.md
```

---

## 🗒️ Usage Guide

1. **Open** the app at `http://localhost:3000`
2. **Scroll** through the cinematic 3D landing page
3. **Upload** your CSV, JSON, or Excel file — or try a built-in sample dataset
4. **PII Vault** — If personal data is detected, choose columns to pseudonymise before proceeding
5. **Review** detected anomalies with AI-generated explanations, SHAP attributions, and threat scores
6. **Explore** AI-generated insights — statistical profiles, null maps, correlations, and narrative summaries
7. **Clean** the dataset by choosing a strategy: drop, quarantine, winsorize, mask, or impute
8. **Compare** the raw vs cleaned data side-by-side to verify cleaning quality
9. **Edit** data using the review panel for manual corrections
10. **Visualize** distributions, correlation heatmaps, and categorical breakdowns
11. **Query** your data using natural language (e.g., *"Show me all transactions above $10,000"*)
12. **Teach** the AI new business terms for better query understanding
13. **Export** a quality report and download the cleaned CSV

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📜 License

This project is for educational and portfolio purposes.

---

<p align="center">
  Built with ❤️ using <strong>FastAPI</strong>, <strong>Next.js</strong>, <strong>Groq</strong>, and <strong>Three.js</strong>
</p>