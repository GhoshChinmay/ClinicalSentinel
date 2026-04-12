"""
DataSentinel — Shared Test Fixtures
Synthetic DataFrames, temp session directories, and mock helpers.
"""

import os
import sys
import uuid
import shutil
import pytest
import polars as pl
import numpy as np

# Ensure the backend root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Bypass Loky/Joblib CPU counting bug on Windows
os.environ["LOKY_MAX_CPU_COUNT"] = "4"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"


@pytest.fixture
def numeric_df() -> pl.DataFrame:
    """A simple numeric DataFrame with a few clear outliers."""
    np.random.seed(42)
    n = 200
    normal_amount = np.random.normal(50, 10, n - 3)
    # Inject 3 extreme outliers
    amounts = np.concatenate([normal_amount, [500, 600, 700]])
    ages = np.concatenate([np.random.randint(18, 65, n - 3), [200, 210, 220]])
    scores = np.concatenate([np.random.uniform(0, 1, n - 3), [99, 98, 97]])

    return pl.DataFrame(
        {
            "amount": amounts.tolist(),
            "age": [int(a) for a in ages.tolist()],
            "score": scores.tolist(),
            "category": (["A"] * 80 + ["B"] * 60 + ["C"] * 57 + ["ZZRARE"] * 3),
        }
    )


@pytest.fixture
def text_df() -> pl.DataFrame:
    """A DataFrame with text columns to exercise the NLP bridge."""
    return pl.DataFrame(
        {
            "review": [
                "Great product, highly recommend!",
                "Terrible quality, fell apart after one use.",
                "Average item, nothing special.",
                "BEST THING EVER 10/10 WOULD BUY AGAIN!!!",
                "decent",
            ]
            * 25,  # 125 rows (> 100 for TF-IDF to fire)
            "rating": [5, 1, 3, 5, 3] * 25,
            "price": [29.99, 15.00, 22.50, 45.00, 18.75] * 25,
        }
    )


@pytest.fixture
def financial_df() -> pl.DataFrame:
    """A DataFrame with datetime + entity ID columns to test the Velocity Engine."""
    from datetime import datetime, timedelta

    np.random.seed(42)
    n = 100
    base_ts = datetime(2025, 1, 1)
    offsets = sorted(np.random.randint(0, 720, n))
    timestamps = [base_ts + timedelta(hours=int(h)) for h in offsets]
    user_ids = [f"USR-{i % 10:03d}" for i in range(n)]
    amounts = np.random.exponential(100, n).tolist()
    # Make a few burst transactions for one user
    for i in range(95, 100):
        user_ids[i] = "USR-000"
        amounts[i] = 5000.0  # extreme values

    return pl.DataFrame(
        {
            "transaction_date": timestamps,
            "user_id": user_ids,
            "amount": amounts,
            "merchant": ["Shop A"] * 50 + ["Shop B"] * 45 + ["SUSPICIOUS_CORP"] * 5,
        }
    )


@pytest.fixture
def pii_df() -> pl.DataFrame:
    """A DataFrame with PII data (email, SSN) to test the scrubber."""
    return pl.DataFrame(
        {
            "name": ["Alice", "Bob", "Charlie"],
            "email": ["alice@example.com", "bob@test.org", "charlie@corp.net"],
            "ssn": ["123-45-6789", "987-65-4321", "555-12-3456"],
            "amount": [100.0, 200.0, 300.0],
            "is_anomaly": [True, False, True],
            "Threat_Score": [80.0, 10.0, 75.0],
            "AI_Reason": ["Test reason", "", "Another reason"],
        }
    )


@pytest.fixture
def session_dir(tmp_path):
    """Create a temp session directory and return (session_id, session_path)."""
    session_id = str(uuid.uuid4())
    session_path = tmp_path / "sessions" / session_id
    session_path.mkdir(parents=True)
    return session_id, str(session_path)


@pytest.fixture
def session_with_data(numeric_df, tmp_path):
    """Create a session with raw_data.parquet already written."""
    session_id = str(uuid.uuid4())
    # Patch to use tmp_path
    session_path = tmp_path / "sessions" / session_id
    session_path.mkdir(parents=True)

    from engines.detection import process_and_detect

    result = process_and_detect(df=numeric_df, session_id=session_id)

    return session_id, result
