from typing import Any

from app.tools.business_client import BusinessClient


class OfferTool:
    """优惠权益工具只封装业务系统能力，不在 AI 服务内计算真实可办理资格。

    Offer 是否可办理、推荐排序和权益有效期属于业务系统职责；AI 服务通过这个薄
    工具消费结果，便于后续替换成真实 Spring Boot API。
    """

    def __init__(self, client: BusinessClient) -> None:
        self.client = client

    async def query_available_offers(self, user_id: str) -> dict[str, Any]:
        return await self.client.query_available_offers(user_id)

    async def recommend_offers(
        self,
        user_id: str,
        need: str | None = None,
        budget: float | None = None,
    ) -> dict[str, Any]:
        return await self.client.recommend_offers(user_id, need=need, budget=budget)
