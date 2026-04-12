# DataSentinel

DataSentinel is an advanced AI-driven Anomaly Detection and Data Observability platform. It deeply integrates machine learning algorithms with dynamically generated Neuro-Symbolic Logic rules and Large Language Models (LLMs) to identify, explain, and mitigate edge cases, data drift, and anomalies in complex tabular datasets.

**Privacy First Guarantee**: Raw row data NEVER leaves your local server. DataSentinel strictly utilizes schema structures and computed aggregate statistics when querying external APIs (like Groq) for logic generation and reasoning.

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Installation and Setup](#installation-and-setup)
- [Usage (API)](#usage)
- [Project Layout](#project-layout)

---

## Architecture Overview

DataSentinel orchestrates a complex, multi-stage detection pipeline:
1. **Dynamic Neuro-Symbolic Logic Gate**: Generates and applies business rules using ultra-fast LLMs directly based on the dataset schema (e.g., catching obvious impossibilities like negative ages).
2. **Velocity Engine**: Automatically identifies time-series columns and generates velocity aggregations (e.g., moving sums) to trace temporal anomalies.
3. **Machine Learning Pipeline (Scikit-learn via Polars)**: Standardizes normal features and deploys an Isolation Forest, guarded by a smart heuristic shield that prevents "flagging overload" on dirty datasets.
4. **SHAP Explainability**: Reverses the Isolation Forest scoring by computing Shapley additive explanations (SHAP) on anomalous rows, pointing out the exact feature drivers.
5. **Threat Scoring Engine**: Provides absolute normalization from 0.0 to 100.0 utilizing a secondary HistGradientBoostingClassifier.
6. **Insight Engine**: Interprets raw statistics into natural language sentences identifying skewness, missing values, and correlated dimensions.
7. **Semantic Querying**: DuckDB powered SQL execution from natural language strings. 

## Key Features
- Multi-format ingestion (CSV, JSON, Excel) capped to 500MB
- Fast in-memory processing via **Polars**
- Privacy-preserving **PII Scanning** and one-click Pseudonymisation (SHA-256 with salting)
- **Groq Cloud Integration** for instantaneous, fast reasoning execution.
- Extensible React/Next.js frontend with data visualization and an AI query sandbox.
- Rate-limiting and strict API authentication out of the box.

## Tech Stack

### Backend
- **Python 3.10+**
- **FastAPI** (Async Web Server)
- **Polars** (High-performance multi-threaded data frames)
- **Scikit-Learn** / **SHAP** (Isolation Forest & Explainability)
- **DuckDB** (Blazing fast embedded analytical SQL engine)
- **Groq API** (Llama 3 powered Logic generation and Natural SQL conversion)

### Frontend
- **Next.js 14** (App Router)
- **TypeScript**
- **Tailwind CSS** (for styling)

---

## Installation and Setup

### Prerequisites
- Python 3.10 or higher
- Node.js 18+ and `npm`
- A valid **Groq API Key**

### 1. Set up the Backend
```bash
cd backend
python -m venv venv

# Activate venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory:
```env
DS_API_KEY=your_secure_randomly_generated_api_key
GROQ_API_KEY=gsk_your_groq_api_key_here
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Start the Backend Server:
```bash
uvicorn main:app --reload --port 8000
```

### 2. Set up the Frontend
```bash
cd frontend
npm install
```

Create a `.env.local` file in the `frontend/` directory:
```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_API_KEY=your_secure_randomly_generated_api_key
```

Start the Application:
```bash
npm run dev
```

Visit `http://localhost:3000` in your web browser.

---

## Usage

You can safely upload tabular data. It will automatically process rows, extract dynamic rules based on the columns provided, execute anomaly detection, and score each row based on threat. 

You can then investigate specific anomalies on the dashboard or use the Natural Language to SQL query box to explore raw relationships locally via DuckDB. If specific data is deemed unsalvageable or too sensitive, use the Quarantine engine to securely stash away toxic/fraudulent rows out of your raw working table.

## Project Layout

```text
dataset-analyzer/
├── backend/
│   ├── data/                 # Sample datasets
│   ├── engines/              # Core logic modules
│   │   ├── cleaning.py       # Actions: Keep, Trim, Quarantine
│   │   ├── detection.py      # ML pipeline, Isolation Forest, SHAP
│   │   ├── insights.py       # Natural language interpretation of stats
│   │   ├── logic_gate.py     # Deterministic rule generation via LLM
│   │   ├── pii_scanner.py    # Privacy compliance engine
│   │   ├── query.py          # NL to SQL conversion via Groq + DuckDB
│   │   └── ...
│   ├── main.py               # FastAPI entrypoints
│   ├── auth.py               # Security / API verification
│   └── requirements.txt      
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js Pages
│   │   ├── components/       # Distinct atomic tools (Clean, Detection, Insights, etc.)
│   │   ├── services/         # Extracted remote API callers
│   │   ├── hooks/            # Custom React hooks (useViz, useQueryData, etc)
│   │   └── ...
│   └── package.json
└── README.md
```