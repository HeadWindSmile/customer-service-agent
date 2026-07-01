from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_low_confidence_request_returns_clarification_without_tools():
    response = client.post(
        "/api/chat",
        json={
            "user_id": "user_001",
            "session_id": "low-confidence",
            "role": "user",
            "message": "随便看看这个事情",
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["intent"] == "unknown"
    assert data["confidence"] < 0.6
    assert "不能确定" in data["answer"]
    assert data["sources"] == []
    assert data["tool_calls"] == []
