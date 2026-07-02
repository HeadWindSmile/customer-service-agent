from typing import Any

from app.tools.business_client import BusinessClient


class UserTool:
    """用户资料工具只通过业务客户端读取，保持 AI 服务和业务库隔离。"""

    def __init__(self, client: BusinessClient) -> None:
        self.client = client

    async def query_user_profile(self, user_id: str) -> dict[str, Any]:
        return await self.client.query_user_profile(user_id)
