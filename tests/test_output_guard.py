import asyncio

from app.agents.customer_agent import CustomerAgent
from app.agents.router import RouteResult
from app.schemas.chat import ChatRequest


class UnsafeOutputRouter:
    async def route(self, *args, **kwargs):
        return RouteResult(answer="这次故障我们保证赔偿，并且一定免费。")


def test_output_guard_blocks_high_risk_commitment_before_returning_user():
    async def scenario():
        agent = CustomerAgent()
        agent.router = UnsafeOutputRouter()

        response = await agent.handle(
            ChatRequest(
                user_id="u1001",
                session_id="output-guard",
                role="user",
                message="套餐变更什么时候生效？",
            )
        )

        assert response.error == "SAFETY_OUTPUT_BLOCKED"
        assert "转人工客服" in response.answer
        assert response.safety_result["output_safety"]["risk_level"] == "HIGH"
        assert response.tool_calls == []

    asyncio.run(scenario())
