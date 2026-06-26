from app.tools.business_client import MockBusinessClient


class BillTool:
    """账单工具模拟内部账务服务接口，后续可替换为 HTTP client。"""

    def __init__(self, client: MockBusinessClient) -> None:
        self.client = client

    def query_bill(self, user_id: str, month: str) -> dict:
        return self.client.query_bill(user_id, month)

