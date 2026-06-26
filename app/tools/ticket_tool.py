from app.tools.business_client import MockBusinessClient


class TicketTool:
    """工单工具保留售后系统边界，第一阶段只返回 mock 工单。"""

    def __init__(self, client: MockBusinessClient) -> None:
        self.client = client

    def create_ticket(self, user_id: str, issue_type: str, description: str) -> dict:
        return self.client.create_ticket(user_id, issue_type, description)

