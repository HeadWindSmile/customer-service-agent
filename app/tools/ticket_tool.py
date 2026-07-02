from typing import Any

from app.tools.business_client import BusinessClient


class TicketTool:
    """工单工具保留售后系统边界，第一阶段只返回 mock 工单。"""

    def __init__(self, client: BusinessClient) -> None:
        self.client = client

    async def create_ticket(self, user_id: str, issue_type: str, description: str) -> dict[str, Any]:
        return await self.client.create_ticket(user_id, issue_type, description)

    async def query_ticket(self, user_id: str, ticket_id: str) -> dict[str, Any]:
        return await self.client.query_ticket(user_id, ticket_id)
