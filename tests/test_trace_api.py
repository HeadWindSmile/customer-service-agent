import asyncio

from fastapi.testclient import TestClient

from app.agents.customer_agent import CustomerAgent
from app.api import traces as traces_api
from app.events.event_bus import EventBus
from app.events.producer import NoneEventProducer
from app.main import app
from app.observability.trace_repository import TraceRepository
from app.observability.tracing import TraceContext
from app.schemas.chat import ChatRequest


def test_get_trace_endpoint_returns_saved_trace(tmp_path, monkeypatch):
    repository = TraceRepository(storage_dir=str(tmp_path))
    trace = TraceContext.new()
    trace.add_attribute("intent", "faq_query")
    trace.finish()
    repository.save(trace)
    monkeypatch.setattr(traces_api, "trace_repository", repository)

    client = TestClient(app)
    response = client.get(f"/api/traces/{trace.trace_id}")

    assert response.status_code == 200
    assert response.json()["trace_id"] == trace.trace_id
    assert response.json()["attributes"]["intent"] == "faq_query"


def test_chat_writes_replayable_trace_file(tmp_path):
    async def scenario():
        repository = TraceRepository(storage_dir=str(tmp_path))
        agent = CustomerAgent(event_bus=EventBus(NoneEventProducer()))
        agent.trace_repository = repository

        response = await agent.handle(
            ChatRequest(
                user_id="u1001",
                session_id="trace-chat-test",
                role="user",
                message="查询我的当前套餐",
            )
        )

        trace = repository.get(response.trace_id)
        assert trace is not None
        attributes = trace["attributes"]
        assert attributes["user_id_masked"] == "u***1"
        assert attributes["session_id"] == "trace-chat-test"
        assert attributes["intent"] == "package_query"
        assert attributes["tool_calls"][0]["tool_name"] == "query_user_package"
        assert attributes["event_publish_result"]
        assert any(span["name"] == "tool.call" for span in trace["spans"])

    asyncio.run(scenario())
