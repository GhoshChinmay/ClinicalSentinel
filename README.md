# DataSentinel

DataSentinel is a premium, AI-powered enterprise platform designed for deep dataset analysis, automated anomaly detection, and natural language data querying.

It features a high-end, responsive "Deep Space" visual aesthetic using WebGL and shaders, providing an immersive experience for data scientists and analysts.

## 🚀 Features

- **Automated Anomaly Detection & Threat Scoring**: Uses a robust machine learning ensemble (Isolation Forest) to isolate statistical anomalies. Includes complete feature engineering for NLP structural signals and velocity-based time-series detection.
- **Narrative Synthesis Engine (Zero-Latency AI)**: Bypasses slow LLM row-by-row inferences by fusing SHAP (SHapley Additive exPlanations) mathematical feature impacts with pure deterministic Python logic. Generates lightning-fast, highly context-aware, and row-specific explanations instantly!
- **Natural Language SQL Querying**: Uses local AI (Ollama with **Llama 3**) coupled with DuckDB to translate plain English questions into complex SQL statements, empowering analysts to question their dataset interactively.
- **AI-Powered Insights (Fail-Safe)**: Get an automated, structured OIA (Observation, Insight, Action) summary over the holistic dataset using **Phi-3**. Uses a robust recursive JSON extractor with intelligent session caching to eliminate redundant processing. Includes health-check fallback states if Local LLMs are offline.
- **Advanced Data Sanitization**: Choose from multiple cleaning protocols including a secure **Quarantine Vault** (to isolate anomalies with context tracking), Smart Winsorization, Categorical Masking, Contextual Imputation, and Hard Dropping.
- **Interactive 3D Visualizations & Dynamic Layouts**: Experience a premium aesthetic interface featuring 3D flip-animations, SHAP impact distribution graphs, active Threat Score threshold sliders, and responsive grid layouts built natively in React.

## 🛠 Tech Stack

### Frontend
- **Framework**: Next.js (React)
- **Styling**: Tailwind CSS v4, Framer Motion, Vanilla CSS (Custom Shaders & Glassmorphism)
- **Components**: Lucide React (Icons), AG Grid (Data Tables), Recharts (Data Visualizations)
- **Architecture**: Context API state management with robust client-side validation and responsive error handling.

### Backend
- **Framework**: FastAPI (Python)
- **Data Engines**: Polars (Ultra-fast DataFrame processing) & Pandas (Scikit-learn interop) & DuckDB (In-memory SQL proxy)
- **Machine Learning**: Scikit-Learn (Isolation Forest), SHAP (Mathematical Transparency)
- **Generative AI**: Ollama (Phi-3 for Holistic Insights, Llama 3 for NLQ)
- **Testing**: fully comprehensive `pytest` suite ensuring 100% CI/CD pipeline readiness across detection, cleaning, queries, insights, and schema engines.

## 🔐 Security & Hardening

### API Key Authentication (Opt-In)
DataSentinel ships with an opt-in API key gate. When the `DS_API_KEY` environment variable is set, every protected endpoint requires a matching `X-API-Key` request header. When it is **not** set (the default), all endpoints remain open — zero friction for local development.

```bash
# Generate a strong key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set these in your `.env` files to activate:
```env
# Backend (.env)
DS_API_KEY=your-generated-key

# Frontend (.env.local)
NEXT_PUBLIC_API_KEY=your-generated-key
```

### Per-Endpoint Rate Limiting
All endpoints are rate-limited via `slowapi` (in-memory, per-IP) to prevent CPU exhaustion and abuse:

| Tier | Limit | Endpoints |
|------|-------|-----------|
| **Heavy CPU** | 10 req/min | `/api/upload/`, `/api/load-sample/` |
| **LLM-bound** | 20 req/min | `/api/insights/`, `/api/report/`, `/api/query/`, `/api/confirm-edit/` |
| **Standard** | 120 req/min | All other protected endpoints |

Public endpoints (`/`, `/api/health`, `/api/samples`) are exempt from authentication but still rate-limited.

## 📦 Installation & Setup

### Prerequisites
- Node.js v20+
- Python 3.10+
- [Ollama](https://ollama.com/) (Required for holistic AI insights and NLP SQL Queries)

### 1. Clone the Repository
```bash
git clone https://github.com/GhoshChinmay/DataSentinel.git
cd DataSentinel
```

### 2. Setup the Backend
Navigate to the `backend` directory and ensure Ollama is installed.

```bash
cd backend
python -m venv venv

# Activate Virtual Environment (Windows)
venv\Scripts\activate
# Activate Virtual Environment (Mac/Linux)
source venv/bin/activate

pip install -r requirements.txt
```

Copy the example environment file and adjust as needed:
```bash
cp ../.env.example .env
```

*Note: Make sure Ollama is installed and run `ollama pull llama3` and `ollama pull phi3` to download your models in the background.*

Start the backend server:
```bash
uvicorn main:app --reload --port 8000
```

> **Tip:** To enable API key protection on a shared/deployed instance, set `DS_API_KEY` in your `.env` file and the matching `NEXT_PUBLIC_API_KEY` on the frontend. See [Security & Hardening](#-security--hardening) for details.

### 3. Setup the Frontend
Open a new terminal and navigate to the `frontend` folder.

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at [http://localhost:3000](http://localhost:3000) and the backend API on [http://localhost:8000](http://localhost:8000).

## 💡 How It Works

1. **Upload**: Drag and drop a raw CSV dataset. The backend streams the file, reading it with Polars for high-speed parsing.
2. **Analysis**: The intelligent Threat Engine applies NLP structurization, time-series velocity tracking, and core numeric evaluation. It calculates Shapley values to pinpoint the exact driver.
3. **Synthesis**: The Narrative Synthesis generator loops over SHAP values and pre-calculated Z-scores to instantly write dynamic explanation strings.
4. **AI Consultation**: The local Llama 3/Phi-3 model provides global macroeconomic text explanations and allows NLP-based SQL filtering directly on the records.
5. **Export**: Easily export pristine, anomaly-free datasets (minus any synthetic background features) ready for downstream dashboarding.