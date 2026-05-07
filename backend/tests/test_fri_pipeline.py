import os
import pytest
import polars as pl
from engines.fri_calculator import calculate_fri_report

@pytest.fixture
def sample_dataset():
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    file_path = os.path.join(data_dir, "clinical_trial_sample.csv")
    if not os.path.exists(file_path):
        pytest.skip("Clinical trial sample dataset not found")
    return pl.read_csv(file_path, infer_schema_length=10000)

def test_fri_pipeline(sample_dataset):
    df = sample_dataset
    
    # Adding mock internal columns so that they get filtered properly
    df = df.with_columns([
        pl.lit(False).alias("is_anomaly"),
        pl.lit(0.0).alias("Threat_Score")
    ])

    result = calculate_fri_report(df)
    
    assert "investigators" in result
    assert "summary" in result
    
    summary = result["summary"]
    assert summary["total_investigators"] > 0
    
    # We assert that the fri_score calculation ran without crashing
    for inv_id, data in result["investigators"].items():
        assert "fri_score" in data
        assert "risk_band" in data
        assert "narrative" in data
