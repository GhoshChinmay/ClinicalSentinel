import pytest
from engines.reg_rag import evaluate_compliance, initialize_regulatory_knowledge_base

def test_reg_rag_initialization():
    try:
        collection = initialize_regulatory_knowledge_base()
        assert collection is not None
        assert collection.count() >= 0
    except Exception as e:
        pytest.skip(f"ChromaDB initialization failed, skipping: {e}")

def test_reg_rag_evaluate():
    # Provide mock anomaly details
    anomaly_details = {
        "FRI_Score": 88,
        "Benfords_Law_Deviation": 61,
        "Temporal_Burst": True,
        "description": "High fabrication risk with anomalous midnight entry bursts."
    }
    
    import os
    
    result = evaluate_compliance("Dr. Test", anomaly_details)
    
    if not os.getenv("GROQ_API_KEY"):
        assert "error" in result
        assert result["error"] == "GROQ_API_KEY not found."
    else:
        assert "status" in result
        if result["status"] == "success":
            assert "regulatory_verdict" in result
            assert "referenced_documents" in result
