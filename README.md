# ClinicalSentinel ⚕️🔬

ClinicalSentinel is an advanced, production-ready, patentable forensic audit platform specifically designed for clinical trials and EDC (Electronic Data Capture) systems. It utilizes a highly sophisticated 7-layer anomaly detection pipeline to uncover subtle data fabrication, temporal manipulation, cohort drift, and collusion networks, providing out-of-the-box 21 CFR Part 11 compliant audit reports.

---

## 🚀 The 7-Layer Forensic Intelligence Architecture

ClinicalSentinel extends beyond traditional range-checks by implementing seven specialized modules designed to detect multi-dimensional fraud patterns:

*   **F1: X-FRI (Explainable Fabrication Risk Index)**
    *   Decomposes the overall Fabrication Risk Index (FRI) using SHAP values. Understand *why* an investigator was flagged and what specific metrics (e.g., Blood Pressure, Heart Rate) drove the anomaly score.
*   **F2: GNN-Collusion Detector**
    *   Graph Neural Network (GNN) based approach to identify collusion rings. Analyzes shared attributes (e.g., shared Site ID, CRO) to map out networks of suspicious investigators who may be coordinating fraudulent data entry.
*   **F3: WearableGate (Authentication)**
    *   Validates high-frequency biometric data (e.g., from wearables or continuous monitors) for biologically plausible noise and physical consistency, ensuring the data wasn't synthetically generated.
*   **F4: RegRAG (Regulatory Compliance Auto-Checker)**
    *   A Retrieval-Augmented Generation (RAG) engine powered by Groq and ChromaDB. It cross-references detected anomalies against statutory documents (FDA 21 CFR Part 11, ICH E6(R3), DPDP Act) and generates legal compliance verdicts.
*   **F5: CohortDrift**
    *   Identifies when a specific cohort (e.g., patients at a specific site) begins to drift statistically from the study-wide baseline or established historical norms, signaling potential systemic manipulation.
*   **F6: SynthAudit (Synthetic Reference Baselines)**
    *   Uses SDV (Synthetic Data Vault) to generate a statistically perfect "clean" baseline from trusted historical clinical data. Investigator data is then audited against this synthetic baseline to detect deviations.
*   **F7: InvestiProfile (Longitudinal Behavioral Profiling)**
    *   Builds behavioral profiles for individual investigators over time, identifying sudden behavioral shifts like "Night Shift" data entries, "Speed Typing" (impossible entry volumes), or "Weekend Warrior" patterns.

---

## 🛠️ Tech Stack

*   **Backend:** FastAPI, Python, Polars (for high-performance data processing)
*   **Frontend:** Next.js (React), Tailwind CSS, Framer Motion, Plotly
*   **Machine Learning:** PyTorch (GNNs), scikit-learn, PyOD, SHAP, SDV
*   **LLM Integration:** LangChain, Groq (LPU Inference), HuggingFace Embeddings, ChromaDB (Vector Store)
*   **Report Generation:** fpdf2 (21 CFR Part 11 Compliant PDFs)

---

## ⚙️ Installation & Setup

### Prerequisites
*   Node.js (v18+)
*   Python (3.10+)

### 1. Backend Setup
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
```

**Environment Variables (`backend/.env`):**
```ini
DS_API_KEY=your_secure_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

**Run Backend:**
```bash
uvicorn main:app --reload
```
*API will run on `http://127.0.0.1:8000`*

### 2. Frontend Setup
```bash
cd frontend
npm install
```

**Environment Variables (`frontend/.env.local`):**
```ini
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_API_KEY=your_secure_api_key_here
```

**Run Frontend:**
```bash
npx next dev
```
*App will run on `http://localhost:3000`*

---

## ⚖️ Compliance

ClinicalSentinel is built with **FDA 21 CFR Part 11** and **ICH E6(R3)** compliance in mind.
*   All PDF reports contain system-generated UTC timestamps.
*   Scores are mathematically reproducible given the same dataset and seed variables.
*   The system maintains strict isolation of user session datasets to ensure data integrity during analysis.

---
*Developed by GhoshChinmay.*