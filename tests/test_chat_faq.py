from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def post_chat(message: str):
    return client.post(
        "/api/chat",
        json={
            "user_id": "user_001",
            "session_id": "rag-chat",
            "role": "user",
            "message": message,
        },
    )


def test_faq_query_returns_real_knowledge_sources():
    response = post_chat("套餐变更什么时候生效？")
    data = response.json()

    assert response.status_code == 200
    assert data["intent"] == "faq_query"
    assert data["sources"]
    assert data["sources"][0]["metadata"]["source"].startswith("data/knowledge/")
    assert "套餐" in data["answer"]


def test_billing_faq_uses_billing_policy_source():
    data = post_chat("账单里为什么会有超量流量费用？").json()

    assert data["intent"] == "faq_query"
    assert data["sources"][0]["title"] == "账单政策说明"
    assert "超量" in data["sources"][0]["content"]


def test_fault_diagnosis_returns_real_fault_source_metadata():
    data = post_chat("宽带连不上应该怎么排查？").json()

    assert data["intent"] == "fault_diagnosis"
    assert data["sources"]
    assert data["sources"][0]["title"] == "故障排查说明"
    assert data["sources"][0]["metadata"]["section"] == "宽带无法上网"
