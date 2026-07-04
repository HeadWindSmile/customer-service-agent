import asyncio

from app.agents.customer_agent import CustomerAgent
from app.schemas.chat import ChatRequest


def test_user_package_query_self_checks_self_permission():
    async def scenario():
        agent = CustomerAgent()
        response = await agent.handle(
            ChatRequest(
                user_id="u1001",
                session_id="rbac-user-package",
                role="user",
                message="查询我的当前套餐",
            )
        )

        assert response.error is None
        assert response.tool_calls[0].permission == "PACKAGE_QUERY_SELF"
        assert response.tool_calls[0].permission_checked is True
        assert response.tool_calls[0].audit_logged is False

    asyncio.run(scenario())


def test_user_bill_query_self_is_allowed_and_audited():
    async def scenario():
        agent = CustomerAgent()
        response = await agent.handle(
            ChatRequest(
                user_id="u1001",
                session_id="rbac-user-bill",
                role="user",
                target_user_id="u1001",
                message="帮我查本月账单",
            )
        )

        assert response.error is None
        assert response.tool_calls[0].permission == "BILL_QUERY_SELF"
        assert response.tool_calls[0].permission_checked is True
        assert response.tool_calls[0].audit_logged is True

    asyncio.run(scenario())


def test_user_offer_query_self_checks_offer_permission_without_audit():
    async def scenario():
        agent = CustomerAgent()
        response = await agent.handle(
            ChatRequest(
                user_id="u1001",
                session_id="rbac-user-offer",
                role="user",
                message="我有哪些可办理优惠权益？",
            )
        )

        assert response.error is None
        assert response.tool_calls[0].permission == "OFFER_QUERY_SELF"
        assert response.tool_calls[0].permission_checked is True
        assert response.tool_calls[0].audit_logged is False

    asyncio.run(scenario())


def test_user_order_query_self_is_allowed_and_audited():
    async def scenario():
        agent = CustomerAgent()
        response = await agent.handle(
            ChatRequest(
                user_id="u1001",
                session_id="rbac-user-order",
                role="user",
                message="帮我查订单 ORD-20260701001 的状态",
            )
        )

        assert response.error is None
        assert response.tool_calls[0].permission == "ORDER_QUERY_SELF"
        assert response.tool_calls[0].permission_checked is True
        assert response.tool_calls[0].audit_logged is True

    asyncio.run(scenario())
