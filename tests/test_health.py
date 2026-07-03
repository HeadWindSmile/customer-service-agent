from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint_returns_app_status():
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"]
    assert data["version"]
    assert data["uptime_seconds"] >= 0


def test_metrics_lite_returns_single_process_snapshot():
    client.get("/health")

    response = client.get("/metrics-lite")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["scope"] == "single_process"
    assert data["total_requests"] >= 1
    assert "GET /health" in data["paths"]
