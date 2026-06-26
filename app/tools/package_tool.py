from app.tools.business_client import MockBusinessClient


class PackageTool:
    """套餐工具封装业务系统调用，避免 Router 直接依赖底层客户端细节。"""

    def __init__(self, client: MockBusinessClient) -> None:
        self.client = client

    def query_user_package(self, user_id: str) -> dict:
        return self.client.query_user_package(user_id)

    def change_package(self, user_id: str, target_package: str) -> dict:
        return self.client.change_package(user_id, target_package)

