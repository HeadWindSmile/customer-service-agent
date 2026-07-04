import asyncio

from app.agents.customer_agent import CustomerAgent
from app.schemas.chat import ChatRequest


def test_agent_can_query_target_bill_with_agent_permission():
    async def scenario():
        agent = CustomerAgent()
        response = await agent.handle(
            ChatRequest(
                user_id="agent001",
                session_id="rbac-agent-bill",
                role="agent",
                target_user_id="u1002",
                message="帮客户查本月账单",
            )
        )

        assert response.error is None
        call = response.tool_calls[0]
        assert call.input["user_id"] == "u***2"
        assert call.permission == "BILL_QUERY_AGENT"
        assert call.permission_checked is True
        assert call.audit_logged is True

    asyncio.run(scenario())


def test_agent_can_create_ticket_for_target_user_with_audit():
    async def scenario():
        agent = CustomerAgent()
        response = await agent.handle(
            ChatRequest(
                user_id="agent001",
                session_id="rbac-agent-ticket",
                role="agent",
                target_user_id="u1002",
                message="帮客户创建宽带断网工单",
            )
        )

        assert response.error is None
        call = response.tool_calls[0]
        assert call.tool_name == "create_ticket"
        assert call.permission == "TICKET_CREATE_AGENT"
        assert call.audit_logged is True

    asyncio.run(scenario())


def test_admin_can_change_package_for_target_user():
    async def scenario():
        agent = CustomerAgent()
        response = await agent.handle(
            ChatRequest(
                user_id="admin001",
                session_id="rbac-admin-package-change",
                role="admin",
                target_user_id="u1002",
                message="帮客户办理5G畅享套餐",
            )
        )

        assert response.error is None
        call = response.tool_calls[0]
        assert call.permission == "PACKAGE_CHANGE_AGENT"
        assert call.permission_checked is True
        assert call.audit_logged is True

    asyncio.run(scenario())


def test_agent_can_query_target_order_with_audit():
    async def scenario():
        agent = CustomerAgent()
        response = await agent.handle(
            ChatRequest(
                user_id="agent001",
                session_id="rbac-agent-order",
                role="agent",
                target_user_id="u1001",
                message="帮客户查订单 ORD-20260701001 的状态",
            )
        )

        assert response.error is None
        call = response.tool_calls[0]
        assert call.input["user_id"] == "u***1"
        assert call.permission == "ORDER_QUERY_AGENT"
        assert call.permission_checked is True
        assert call.audit_logged is True

    asyncio.run(scenario())


def test_agent_can_recommend_offer_for_target_user_with_audit():
    async def scenario():
        agent = CustomerAgent()
        response = await agent.handle(
            ChatRequest(
                user_id="agent001",
                session_id="rbac-agent-offer",
                role="agent",
                target_user_id="u1001",
                message="帮客户推荐一个流量优惠",
            )
        )

        assert response.error is None
        call = response.tool_calls[0]
        assert call.tool_name == "recommend_offers"
        assert call.permission == "OFFER_RECOMMEND_AGENT"
        assert call.audit_logged is True

    asyncio.run(scenario())
