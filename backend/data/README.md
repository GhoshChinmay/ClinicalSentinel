# Test Data

This directory contains sample CSV datasets for local development and testing.

**These files are NOT tracked by git** (blocked by `*.csv` in `.gitignore`).

## Files

| File | Size | Description |
|------|------|-------------|
| `creditcard.csv` | ~144 MB | Credit card fraud detection dataset (Kaggle) |
| `amazon.csv` | ~4.5 MB | Amazon product review dataset |
| `Titanic-Dataset.csv` | ~60 KB | Classic Titanic passenger dataset |
| `velocity_engine.csv` | ~1.4 KB | Small synthetic dataset for velocity engine testing |
| `bad_data.csv` | ~0.1 KB | Intentionally malformed CSV for schema validation testing |

## Usage

Upload any of these files through the DataSentinel web UI at `http://localhost:3000`.

> **Note:** Do not commit CSV files to the repository. If you need to share test data, use a cloud storage link or Git LFS.
