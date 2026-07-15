from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_metrics_endpoint_returns_prometheus_text():
    client.get("/health")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "# HELP customer_service_agent_http_requests_total" in body
    assert "# TYPE customer_service_agent_http_request_latency_seconds histogram" in body
    assert 'customer_service_agent_http_requests_total{method="GET",path="/health",status="200"}' in body
    assert "customer_service_agent_http_request_latency_seconds_bucket" in body
    assert 'le="+Inf"' in body
