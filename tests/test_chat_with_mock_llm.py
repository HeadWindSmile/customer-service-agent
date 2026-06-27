from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def post_chat(message: str):
    return client.post(
        "/api/chat",
        json={
            "user_id": "user_001",
            "session_id": "mock-llm-chat",
            "role": "user",
            "message": message,
        },
    )


def test_chat_faq_uses_mock_llm_answer_chain():
    response = post_chat("套餐变更什么时候生效？")
    data = response.json()

    assert response.status_code == 200
    assert data["intent"] == "faq_query"
    assert data["sources"]
    assert "根据知识库《" in data["answer"]
    assert data["tool_calls"] == []


def test_chat_fault_diagnosis_uses_rag_answer_chain():
    data = post_chat("宽带连不上应该怎么排查？").json()

    assert data["intent"] == "fault_diagnosis"
    assert data["sources"]
    assert "建议" in data["answer"]
    assert "工单" in data["answer"]


def test_business_tool_route_is_not_changed_by_llm_stage():
    data = post_chat("查询我的当前套餐").json()

    assert data["intent"] == "package_query"
    assert data["sources"] == []
    assert data["tool_calls"][0]["tool_name"] == "query_user_package"
