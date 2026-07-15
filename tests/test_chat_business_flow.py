import asyncio

import httpx

from app.agents.customer_agent import CustomerAgent
from app.agents.router import CustomerRouter
from app.schemas.chat import ChatRequest
from app.tools.business_client import HttpBusinessClient
from mock_business_service.main import app as business_app


def _agent_with_http_business_client() -> CustomerAgent:
    transport = httpx.ASGITransport(app=business_app)
    business_client = HttpBusinessClient("http://business.test", timeout_ms=800, transport=transport)
    agent = CustomerAgent()
    agent.router = CustomerRouter(business_client=business_client)
    return agent


def test_chat_package_query_uses_http_business_client_and_records_tool_call():
    agent = _agent_with_http_business_client()
    request = ChatRequest(
        user_id="u1001",
        session_id="phase5-package-query",
        role="user",
        message="查询我的当前套餐",
    )

    response = asyncio.run(agent.handle(request))

    assert response.intent == "package_query"
    assert response.error is None
    assert response.tool_calls[0].tool_name == "query_user_package"
    assert response.tool_calls[0].success is True
    assert response.tool_calls[0].output["package_name"] == "5G畅享套餐"
    assert response.tool_calls[0].latency_ms >= 0


def test_chat_bill_query_records_business_failure_in_tool_call():
    agent = _agent_with_http_business_client()
    request = ChatRequest(
        user_id="u1001",
        session_id="phase5-bill-missing",
        role="user",
        message="帮我查2099-01账单",
    )

    response = asyncio.run(agent.handle(request))

    assert response.intent == "bill_query"
    assert response.error is None
    assert response.tool_calls[0].tool_name == "query_bill"
    assert response.tool_calls[0].success is False
    assert response.tool_calls[0].output["error_code"] == "BILL_NOT_FOUND"
    assert response.tool_calls[0].error_message == "账单不存在。"
    assert "账单查询失败" in response.answer


def test_chat_offer_query_uses_http_business_client_and_records_tool_call():
    agent = _agent_with_http_business_client()
    request = ChatRequest(
        user_id="u1001",
        session_id="phase16-offer-query",
        role="user",
        message="我有哪些可办理优惠权益？",
    )

    response = asyncio.run(agent.handle(request))

    assert response.intent == "offer_query"
    assert response.error is None
    call = response.tool_calls[0]
    assert call.tool_name == "query_available_offers"
    assert call.success is True
    assert call.output["offers"]
    assert call.permission == "OFFER_QUERY_SELF"


def test_chat_offer_recommend_uses_http_business_client():
    agent = _agent_with_http_business_client()
    request = ChatRequest(
        user_id="u1001",
        session_id="phase16-offer-recommend",
        role="user",
        message="我流量不够，预算20元以内，推荐一个优惠",
    )

    response = asyncio.run(agent.handle(request))

    assert response.intent == "offer_recommend"
    assert response.error is None
    assert response.tool_calls[0].tool_name == "recommend_offers"
    assert response.tool_calls[0].output["offers"][0]["offer_id"] == "OFF-DATA-20G"


def test_chat_order_query_uses_http_business_client_and_audit():
    agent = _agent_with_http_business_client()
    request = ChatRequest(
        user_id="agent001",
        session_id="phase16-order-query",
        role="agent",
        target_user_id="u1001",
        message="帮客户查订单 ORD-20260701001 的状态",
    )

    response = asyncio.run(agent.handle(request))

    assert response.intent == "order_query"
    assert response.error is None
    call = response.tool_calls[0]
    assert call.tool_name == "query_order"
    assert call.output["order_id"] == "ORD-20260701001"
    assert call.permission == "ORDER_QUERY_AGENT"
    assert call.audit_logged is True
