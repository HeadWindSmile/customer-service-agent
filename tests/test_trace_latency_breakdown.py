import asyncio

from app.agents.customer_agent import CustomerAgent
from app.events.event_bus import EventBus
from app.events.producer import NoneEventProducer
from app.observability.trace_repository import TraceRepository
from app.observability.tracing import LATENCY_BREAKDOWN_STAGES, TraceContext
from app.schemas.chat import ChatRequest


def test_trace_context_builds_latency_breakdown_for_known_stages():
    trace = TraceContext.new()
    input_span = trace.start_span("safety.input")
    trace.end_span(input_span)
    route_span = trace.start_span("router.route")
    trace.end_span(route_span)
    trace.finish()

    breakdown = trace.attributes["latency_breakdown"]

    assert set(LATENCY_BREAKDOWN_STAGES).issubset(breakdown["stages"])
    assert breakdown["stages"]["safety.input"]["count"] == 1
    assert breakdown["stages"]["router.route"]["inclusive"] is True
    assert breakdown["stages"]["tool.call"]["status"] == "not_run"
    assert breakdown["total_latency_ms"] >= 0


def test_chat_trace_contains_latency_breakdown_for_tool_flow(tmp_path):
    async def scenario():
        repository = TraceRepository(storage_dir=str(tmp_path))
        agent = CustomerAgent(event_bus=EventBus(NoneEventProducer()))
        agent.trace_repository = repository

        response = await agent.handle(
            ChatRequest(
                user_id="u1001",
                session_id="latency-breakdown",
                role="user",
                message="查询我的当前套餐",
            )
        )

        trace = repository.get(response.trace_id)
        assert trace is not None
        breakdown = trace["attributes"]["latency_breakdown"]
        stages = breakdown["stages"]
        assert stages["safety.input"]["count"] == 1
        assert stages["memory.load"]["count"] == 1
        assert stages["intent.classify"]["count"] == 1
        assert stages["tool.call"]["count"] == 1
        assert stages["memory.save"]["count"] == 1
        assert stages["event.publish"]["count"] >= 1

    asyncio.run(scenario())
