from dataclasses import replace

from fastapi.testclient import TestClient

from app.health import checks
from app.main import app


client = TestClient(app)


def test_ready_endpoint_returns_structured_dependency_checks():
    response = client.get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["ready"] is True
    for key in [
        "app",
        "memory",
        "business_service",
        "vector_store",
        "llm_provider",
        "event_producer",
        "trace_storage",
    ]:
        assert key in data["checks"]
        assert "status" in data["checks"][key]


def test_ready_marks_configured_business_service_failure_as_not_ready(monkeypatch):
    monkeypatch.setattr(
        checks,
        "settings",
        replace(checks.settings, business_service_base_url="http://127.0.0.1:1"),
    )

    response = client.get("/ready")

    assert response.status_code == 503
    data = response.json()
    assert data["ready"] is False
    assert data["checks"]["business_service"]["status"] == "failed"
