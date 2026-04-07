"""
DataSentinel — API Integration Tests
FastAPI TestClient tests for upload, data retrieval, health check, and error handling.
"""

import io
import csv
import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def csv_bytes():
    """Generate a valid 3-column CSV as bytes for upload testing."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "value", "category"])
    for i in range(50):
        writer.writerow([f"item_{i}", i * 10, "A" if i % 2 == 0 else "B"])
    # Add outliers
    writer.writerow(["outlier_1", 99999, "RARE_CAT"])
    writer.writerow(["outlier_2", 88888, "RARE_CAT"])
    writer.writerow(["outlier_3", 77777, "RARE_CAT"])
    return output.getvalue().encode("utf-8")


class TestRootEndpoint:
    def test_root_returns_status(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "status" in response.json()


class TestHealthEndpoint:
    def test_health_returns_ollama_status(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "ollama" in data
        assert isinstance(data["ollama"], bool)
        assert "models" in data


class TestUploadEndpoint:
    def test_upload_csv_success(self, client, csv_bytes):
        response = client.post(
            "/api/upload/",
            files={"file": ("test.csv", csv_bytes, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "session_id" in data
        assert "anomaly_count" in data

    def test_upload_too_large_rejected(self, client):
        """Files over 100MB should be rejected."""
        # Generate a >100MB payload. We use a smaller synthetic one but patch the limit.
        # In practice, a real 100MB+ file would be needed, but we test the logic.
        large_content = b"x" * (101 * 1024 * 1024)
        response = client.post(
            "/api/upload/",
            files={"file": ("huge.csv", large_content, "text/csv")},
        )
        assert response.status_code == 413

    def test_upload_invalid_json(self, client):
        """Invalid JSON should return 400."""
        bad_json = b'{"invalid": true, "not_an_array": "oops"}'
        response = client.post(
            "/api/upload/",
            files={"file": ("bad.json", bad_json, "application/json")},
        )
        assert response.status_code == 400


class TestDataEndpoint:
    def test_invalid_session_id_rejected(self, client):
        response = client.get("/api/data/not-a-valid-uuid")
        assert response.status_code == 400
        assert "Invalid session ID" in response.json()["error"]

    def test_missing_session_returns_404(self, client):
        response = client.get("/api/data/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


class TestCleanEndpoint:
    def test_clean_invalid_session(self, client):
        response = client.post("/api/clean/../etc/passwd?action=drop")
        # Path traversal attempt either gets 400 (invalid UUID) or 404
        assert response.status_code in (400, 404)


class TestSamplesEndpoint:
    def test_list_samples(self, client):
        response = client.get("/api/samples")
        assert response.status_code == 200
        data = response.json()
        assert "samples" in data
        assert isinstance(data["samples"], list)
