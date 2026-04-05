# DataSentinel

DataSentinel is a premium, AI-powered enterprise platform designed for deep dataset analysis, automated anomaly detection, and natural language data querying.

It features a high-end, responsive "Deep Space" visual aesthetic using WebGL and shaders, providing an immersive experience for data scientists and analysts.

## 🚀 Features

- **Automated Anomaly Detection**: Uses state-of-the-art algorithms (Isolation Forest, Local Outlier Factor, and HistGradientBoostingClassifier) to flag anomalies intelligently and assigns an AI-generated reason for each flagged anomaly.
- **Natural Language SQL Querying**: Uses local AI (Ollama with Llama 3) coupled with DuckDB to translate plain English queries into complex SQL statements, allowing for dynamic filtering, selecting, and even updating dataset records interactively.
- **AI-Powered Insights (Fail-Safe)**: Get an automated structured OIA (Observation, Insight, Action) summary of your dataset. Uses a robust recursive JSON extractor with fuzzy key matching to handle arbitrary local LLM outputs, coupled with intelligent session caching to eliminate redundant processing.
- **Advanced Data Sanitization**: Choose from multiple cleaning protocols including a secure **Quarantine Vault** (to audit isolated anomalies), Smart Winsorization, Categorical Masking, Contextual Imputation, and Hard Dropping.
- **Interactive 3D Visualizations**: Experience a premium interface featuring 3D flip-animations that explain complex statistical cleaning methods in plain English, paired with Recharts and AG Grid for statistical distributions.
- **High-Performance Architecture**: Backend built with Python (FastAPI, Polars, DuckDB) capable of processing millions of rows quickly with resilient fallback parsing.

## 🛠 Tech Stack

### Frontend
- **Framework**: Next.js 16 (React 19)
- **Styling**: Tailwind CSS v4, Framer Motion, Vanilla CSS (Custom Shaders & Glassmorphism)
- **Components**: Lucide React (Icons), AG Grid (Data Tables), Recharts (Data Visualizations)
- **Architecture**: App Router with strict TypeScript typing

### Backend
- **Framework**: FastAPI (Python)
- **Data Engines**: Polars (Ultra-fast DataFrame processing) & DuckDB (In-memory analytical SQL)
- **Machine Learning**: Scikit-Learn (Anomaly Detection & Classification Engines)
- **Generative AI**: Ollama (Local Llama 3 for Natural Language Queries and Insights)

## 📦 Installation & Setup

### Prerequisites
- Node.js v20+
- Python 3.10+
- [Ollama](https://ollama.com/) (Required for AI insights and NLP SQL Queries)

### 1. Clone the Repository
```bash
git clone https://github.com/GhoshChinmay/DataSentinel.git
cd DataSentinel
```

### 2. Setup the Backend
Navigate to the `backend` directory and ensure Ollama is running.

```bash
cd backend
python -m venv venv

# Activate Virtual Environment (Windows)
venv\Scripts\activate
# Activate Virtual Environment (Mac/Linux)
source venv/bin/activate

pip install -r requirements.txt
```
*Note: Make sure Ollama is installed and the llama3 model is downloaded by running `ollama pull llama3`.*

Start the backend server:
```bash
fastapi dev main.py
# If using uvicorn directly: uvicorn main:app --reload --port 8000
```

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
2. **Analysis**: The intelligent Threat Engine evaluates numeric and categorical distributions, highlighting statistical outliers and calculating risk scores.
3. **AI Consultation**: Ollama provides high-level text explanations and allows NLP-based SQL filtering directly on the records.
4. **Export**: Easily export clean, anomaly-free datasets ready for downstream AI training or dashboarding.