from app.agents.intent_schema import SUPPORTED_INTENTS
from app.agents.router import CustomerRouter
from app.schemas.chat import IntentResult


def test_router_registers_all_supported_intents():
    router = CustomerRouter()

    assert set(router.routes.keys()) == SUPPORTED_INTENTS


def test_bill_explain_routes_to_rag_sources():
    router = CustomerRouter()

    result = router.route(
        IntentResult(intent="bill_explain", slots={}, confidence=0.9, reason="账单解释"),
        "账单里为什么会有超量流量费用？",
        "user_001",
    )

    assert result.sources
    assert result.sources[0].title == "账单政策说明"
    assert result.tool_calls == []


def test_ticket_query_routes_to_mock_business_tool():
    router = CustomerRouter()

    result = router.route(
        IntentResult(
            intent="ticket_query",
            slots={"ticket_id": "TCK-ABC123456"},
            confidence=0.9,
            reason="查询工单",
        ),
        "帮我查工单 TCK-ABC123456 的进度",
        "user_001",
    )

    assert result.tool_calls
    assert result.tool_calls[0].tool_name == "query_ticket"
    assert result.tool_calls[0].output["ticket_id"] == "TCK-ABC123456"
    assert "processing" in result.answer


def test_unknown_route_returns_clarification_without_tool_call():
    router = CustomerRouter()

    result = router.route(
        IntentResult(intent="unknown", slots={}, confidence=0.4, reason="无法确定"),
        "随便看看",
        "user_001",
    )

    assert "不能确定" in result.answer
    assert result.tool_calls == []
    assert result.sources == []
