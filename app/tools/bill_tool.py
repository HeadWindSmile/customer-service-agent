from typing import Any

from app.tools.business_client import BusinessClient


class BillTool:
    """账单工具模拟内部账务服务接口，后续可替换为 HTTP client。"""

    def __init__(self, client: BusinessClient) -> None:
        self.client = client

    async def query_bill(self, user_id: str, month: str) -> dict[str, Any]:
        return await self.client.query_bill(user_id, month)
