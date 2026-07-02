import asyncio

from app.agents.customer_agent import CustomerAgent
from app.schemas.chat import ChatRequest


def test_user_cannot_access_other_user_by_request_target():
    async def scenario():
        agent = CustomerAgent()
        response = await agent.handle(
            ChatRequest(
                user_id="u1001",
                session_id="rbac-forbidden-user-target",
                role="user",
                target_user_id="u1002",
                message="帮我查本月账单",
            )
        )

        assert response.error
        assert "普通用户只能访问自己的业务信息" in response.answer
        assert response.tool_calls == []

    asyncio.run(scenario())


def test_agent_business_query_requires_target_user_id():
    async def scenario():
        agent = CustomerAgent()
        response = await agent.handle(
            ChatRequest(
                user_id="agent001",
                session_id="rbac-forbidden-agent-no-target",
                role="agent",
                message="帮客户查本月账单",
            )
        )

        assert response.error
        assert "必须提供 target_user_id" in response.answer
        assert response.tool_calls == []

    asyncio.run(scenario())


def test_agent_cannot_change_package_without_high_risk_permission():
    async def scenario():
        agent = CustomerAgent()
        response = await agent.handle(
            ChatRequest(
                user_id="agent001",
                session_id="rbac-forbidden-agent-package-change",
                role="agent",
                target_user_id="u1002",
                message="帮客户办理5G畅享套餐",
            )
        )

        assert response.error
        assert "PACKAGE_CHANGE_AGENT" in response.answer
        assert response.tool_calls == []

    asyncio.run(scenario())


def test_request_target_and_slot_target_conflict_is_forbidden():
    async def scenario():
        agent = CustomerAgent()
        response = await agent.handle(
            ChatRequest(
                user_id="agent001",
                session_id="rbac-forbidden-conflict",
                role="agent",
                target_user_id="u1002",
                message="帮用户u1001查本月账单",
            )
        )

        assert response.error
        assert "不一致" in response.answer
        assert response.tool_calls == []

    asyncio.run(scenario())
