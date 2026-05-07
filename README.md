<div align="center">

# ⚕️ ClinicalSentinel

**The Next-Generation Forensic Audit Platform for Clinical Trials**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.12-009688.svg?logo=fastapi&logoColor=white)](#)
[![Next.js](https://img.shields.io/badge/Next.js-React-000000.svg?logo=next.js&logoColor=white)](#)
[![Compliance](https://img.shields.io/badge/Compliance-FDA_21_CFR_Part_11-purple.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#)

*Detect data fabrication, temporal manipulation, and collusion in EDC systems with mathematical precision and AI-driven forensic intelligence.*

[**Features**](#-core-features) • [**The 7-Layer Architecture**](#-the-7-layer-forensic-architecture) • [**Compliance**](#-regulatory-compliance) • [**Installation**](#-installation--setup) • [**Tech Stack**](#-tech-stack)

</div>

---

## 📖 Overview

**ClinicalSentinel** is a highly specialized, patentable forensic intelligence platform designed for the pharmaceutical and clinical research industries. It transcends standard statistical range-checks by implementing a robust, 7-layer anomaly detection pipeline. 

By identifying subtle patterns of data fabrication, identifying cohort drift, mapping collusion networks using Graph Neural Networks, and auto-verifying anomalies against regulatory law via an embedded LLM RAG engine, ClinicalSentinel ensures **uncompromising data integrity** for your clinical trials.

---

## ✨ Core Features

*   **🕵️‍♂️ Multi-Dimensional Fraud Detection:** Identifies data fabrication across numeric, categorical, and temporal dimensions.
*   **⚖️ Automated Regulatory Triage (RegRAG):** Evaluates findings directly against ICH E6(R3) and FDA 21 CFR Part 11 guidelines.
*   **📊 PDF Audit Report Generation:** Automatically synthesizes 21 CFR Part 11 compliant forensic PDF reports, complete with reproducible timestamps.
*   **⚡ Real-Time Processing:** Powered by Polars and FastAPI, handling millions of rows with microsecond latency.
*   **🎨 Premium Intelligence Dashboard:** A sleek, dark-mode Next.js UI showcasing real-time visualizations and SHAP-based AI explanations.

---

## 🧬 The 7-Layer Forensic Architecture

ClinicalSentinel evaluates clinical datasets through seven independent intelligence layers, culminating in a mathematically robust **Fabrication Risk Index (FRI)** for every investigator.

### 🔬 F1: X-FRI (Explainable Fabrication Risk Index)
> **The Explainability Engine**
Decomposes the composite FRI score using **SHAP (SHapley Additive exPlanations)**. X-FRI translates complex machine learning outputs into human-readable narratives, explaining *exactly* which clinical metrics (e.g., Diastolic BP, Heart Rate) drove the anomaly flag.

### 🕸️ F2: GNN-Collusion Detector
> **The Network Mapper**
Leverages **Graph Convolutional Networks (GCNs)** to build relationship graphs between investigators. By mapping shared metadata (e.g., shared trial sites, identical CROs, matching equipment serial numbers), it identifies high-risk "collusion rings" coordinating fraudulent data entry.

### ⌚ F3: WearableGate (Biometric Authentication)
> **The Signal Authenticator**
Analyzes high-frequency biometric data (ECG, continuous glucose monitors, accelerometers). WearableGate checks for natural biological noise, physiological consistency, and physical plausibility to differentiate between genuine patient signals and synthetic/pasted data.

### 📜 F4: RegRAG (Regulatory Compliance Auto-Checker)
> **The Virtual Legal Auditor**
An advanced Retrieval-Augmented Generation (RAG) pipeline powered by **ChromaDB** and **Groq (Llama 3)**. It cross-references detected dataset anomalies against a vector store of statutory laws (FDA 21 CFR Part 11, ICH E6, DPDP Act 2023) to generate immediate, legally grounded compliance verdicts.

### 📉 F5: CohortDrift
> **The Longitudinal Monitor**
Identifies when a specific cohort (e.g., patients from a specific geographic site) statistically deviates from the study-wide baseline over time. Utilizes Kolmogorov-Smirnov (KS) tests and Kullback-Leibler (KL) divergence to spot systemic manipulation.

### 🤖 F6: SynthAudit (Synthetic Reference Baselines)
> **The Perfect Control Group**
Utilizes the **Synthetic Data Vault (SDV)** to generate a statistically flawless "clean" baseline derived from trusted historical clinical data. Investigator data is then audited against this synthetic baseline to detect hyper-subtle deviations that manual monitors miss.

### 🧑‍⚕️ F7: InvestiProfile (Behavioral Profiling)
> **The Human Element Monitor**
Builds longitudinal behavioral profiles for individual investigators. InvestiProfile flags abnormal human data-entry behaviors, including:
> *   🌙 **Night Shifts:** Unexplained bursts of data entry at 3:00 AM.
> *   ⚡ **Speed Typing:** Impossible data entry volumes (e.g., 50 patient vitals entered in 2 minutes).
> *   🏖️ **Weekend Warriors:** Massive data dumping outside of normal clinical operating hours.

---

## 🏛️ Regulatory Compliance

ClinicalSentinel is engineered from the ground up to support submissions to regulatory authorities (FDA, EMA, PMDA).

| Regulation | ClinicalSentinel Coverage |
| :--- | :--- |
| **FDA 21 CFR Part 11** | Secure, system-generated UTC timestamps. Mathematical reproducibility via fixed ML seeds. Non-deterministic models are fully explained via X-FRI. |
| **ICH E6(R3) GCP** | Risk-based quality management (RBQM). Centralized statistical monitoring to identify systematic or significant errors in data collection. |
| **Data Privacy (GDPR/DPDP)** | In-memory processing architecture ensures patient PII/PHI is never leaked or stored improperly. |

---

## 🛠️ Tech Stack

<div align="center">

| Area | Technologies |
| :--- | :--- |
| **Backend & API** | FastAPI, Python 3.10+, Uvicorn |
| **Data Processing** | Polars, NumPy, Pandas |
| **Machine Learning** | PyTorch (PyG), scikit-learn, XGBoost, PyOD |
| **Explainable AI** | SHAP, SDV (Synthetic Data Vault) |
| **GenAI & RAG** | LangChain, Groq (LPU), ChromaDB, HuggingFace |
| **Frontend UI** | Next.js 14, React, Tailwind CSS, Framer Motion |
| **Data Viz** | Plotly.js, Lucide Icons |
| **PDF Export** | fpdf2 |

</div>

---

## 💻 Installation & Setup

### Prerequisites
*   **Node.js** (v18.0 or newer)
*   **Python** (v3.10 or newer)
*   **Git**

### 1. Clone the Repository
```bash
git clone https://github.com/GhoshChinmay/ClinicalSentinel.git
cd ClinicalSentinel
```

### 2. Backend Setup (FastAPI)
Initialize your Python environment and install the required dependencies:

```bash
cd backend
python -m venv venv

# Activate the virtual environment:
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies:
pip install -r requirements.txt
```

**Configure Backend Environment Variables:**
Create a `.env` file in the `backend` directory:
```ini
DS_API_KEY=your_secure_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

**Launch the Backend Engine:**
```bash
uvicorn main:app --reload
```
*The API will start on `http://127.0.0.1:8000`*

### 3. Frontend Setup (Next.js)
Open a new terminal window:

```bash
cd frontend
npm install
```

**Configure Frontend Environment Variables:**
Create a `.env.local` file in the `frontend` directory:
```ini
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_API_KEY=your_secure_api_key_here
```

**Launch the Frontend Dashboard:**
```bash
npx next dev
```
*The web dashboard will be available at `http://localhost:3000`*

---

## 📚 API Architecture Quick Reference

ClinicalSentinel exposes a robust REST API for integrating into existing EDC/CTMS systems:

*   `POST /api/upload`: Ingest clinical datasets (CSV/Parquet).
*   `GET /api/clinical/xfri/{session_id}`: Retrieve SHAP decompositions (F1).
*   `GET /api/clinical/gnn-collusion/{session_id}`: Generate investigator graph edges (F2).
*   `POST /api/clinical/reg-rag/init`: Prime the ChromaDB vector store (F4).
*   `GET /api/download_report/{session_id}`: Generate a 21 CFR Part 11 PDF audit.

---

<div align="center">
  <p><strong>Built with precision for the future of clinical research.</strong></p>
  <p>&copy; 2026 GhoshChinmay. All Rights Reserved.</p>
</div>