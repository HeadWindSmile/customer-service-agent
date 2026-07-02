from typing import Any

from app.tools.business_client import BusinessClient


class PackageTool:
    """套餐工具封装业务系统调用，避免 Router 直接依赖底层客户端细节。"""

    def __init__(self, client: BusinessClient) -> None:
        self.client = client

    async def query_user_package(self, user_id: str) -> dict[str, Any]:
        return await self.client.query_user_package(user_id)

    async def change_package(self, user_id: str, target_package: str) -> dict[str, Any]:
        return await self.client.change_package(user_id, target_package)
