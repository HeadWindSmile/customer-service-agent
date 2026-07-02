import asyncio

from app.agents.customer_agent import CustomerAgent
from app.schemas.chat import ChatRequest


def test_multi_turn_package_question_uses_rewritten_query():
    async def scenario():
        agent = CustomerAgent()
        await agent.handle(
            ChatRequest(
                user_id="u1001",
                session_id="phase6-package-memory",
                role="user",
                message="查询我的当前套餐",
            )
        )

        response = await agent.handle(
            ChatRequest(
                user_id="u1001",
                session_id="phase6-package-memory",
                role="user",
                message="这个套餐什么时候生效？",
            )
        )

        assert response.rewritten_query == "5G畅享套餐什么时候生效？"
        assert response.intent == "faq_query"
        assert response.sources

    asyncio.run(scenario())


def test_multi_turn_ticket_query_uses_last_ticket_id():
    async def scenario():
        agent = CustomerAgent()
        first = await agent.handle(
            ChatRequest(
                user_id="u1001",
                session_id="phase6-ticket-memory",
                role="user",
                message="我要创建工单，宽带断网",
            )
        )
        ticket_id = first.tool_calls[0].output["ticket_id"]

        second = await agent.handle(
            ChatRequest(
                user_id="u1001",
                session_id="phase6-ticket-memory",
                role="user",
                message="刚才那个工单进度怎么样？",
            )
        )

        assert ticket_id in second.rewritten_query
        assert second.intent == "ticket_query"
        assert second.tool_calls[0].tool_name == "query_ticket"

    asyncio.run(scenario())


def test_memory_isolation_uses_user_id_and_session_id_together():
    async def scenario():
        agent = CustomerAgent()
        shared_session = "phase6-isolation"
        await agent.handle(
            ChatRequest(
                user_id="u1001",
                session_id=shared_session,
                role="user",
                message="查询我的当前套餐",
            )
        )

        response = await agent.handle(
            ChatRequest(
                user_id="u1002",
                session_id=shared_session,
                role="user",
                message="这个套餐什么时候生效？",
            )
        )

        assert response.rewritten_query == "这个套餐什么时候生效？"

    asyncio.run(scenario())

