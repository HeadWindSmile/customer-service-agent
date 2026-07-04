from typing import Any

from app.tools.business_client import BusinessClient


class OrderTool:
    """订单工具保留订单域边界，AI 服务不直接读取订单表。

    查询指定订单和最近订单都通过 BusinessClient 完成，避免 Router 依赖 mock 数据
    结构，也方便未来接入真实订单中心。
    """

    def __init__(self, client: BusinessClient) -> None:
        self.client = client

    async def query_order(self, user_id: str, order_id: str) -> dict[str, Any]:
        return await self.client.query_order(user_id, order_id)

    async def query_recent_orders(self, user_id: str, limit: int = 3) -> dict[str, Any]:
        return await self.client.query_recent_orders(user_id, limit=limit)
