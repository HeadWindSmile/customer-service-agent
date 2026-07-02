import asyncio
from typing import Any

from app.tools.bill_tool import BillTool
from app.tools.business_client import BusinessClient
from app.tools.package_tool import PackageTool
from app.tools.ticket_tool import TicketTool


class RecordingBusinessClient(BusinessClient):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def query_user_profile(self, user_id: str) -> dict[str, Any]:
        self.calls.append(("query_user_profile", {"user_id": user_id}))
        return {"user_id": user_id, "name": "测试用户", "level": "gold"}

    async def query_user_package(self, user_id: str) -> dict[str, Any]:
        self.calls.append(("query_user_package", {"user_id": user_id}))
        return {"package_name": "5G畅享套餐", "monthly_fee": 129, "data_quota": "60GB"}

    async def query_bill(self, user_id: str, month: str) -> dict[str, Any]:
        self.calls.append(("query_bill", {"user_id": user_id, "month": month}))
        return {"month": month, "amount": 88.0, "status": "已出账", "items": ["套餐月费"]}

    async def change_package(self, user_id: str, target_package: str) -> dict[str, Any]:
        self.calls.append(("change_package", {"user_id": user_id, "target_package": target_package}))
        return {"order_id": "PKG-TEST", "user_id": user_id, "target_package": target_package, "status": "submitted"}

    async def create_ticket(self, user_id: str, issue_type: str, description: str) -> dict[str, Any]:
        self.calls.append(
            ("create_ticket", {"user_id": user_id, "issue_type": issue_type, "description": description})
        )
        return {"ticket_id": "TCK-TEST", "user_id": user_id, "issue_type": issue_type, "status": "created"}

    async def query_ticket(self, user_id: str, ticket_id: str) -> dict[str, Any]:
        self.calls.append(("query_ticket", {"user_id": user_id, "ticket_id": ticket_id}))
        return {"ticket_id": ticket_id, "user_id": user_id, "status": "processing", "summary": "处理中"}


def test_package_tool_delegates_to_business_client():
    client = RecordingBusinessClient()
    tool = PackageTool(client)

    result = asyncio.run(tool.query_user_package("u1001"))

    assert result["package_name"] == "5G畅享套餐"
    assert client.calls == [("query_user_package", {"user_id": "u1001"})]


def test_bill_tool_delegates_to_business_client():
    client = RecordingBusinessClient()
    tool = BillTool(client)

    result = asyncio.run(tool.query_bill("u1001", "本月"))

    assert result["amount"] == 88.0
    assert client.calls == [("query_bill", {"user_id": "u1001", "month": "本月"})]


def test_ticket_tool_delegates_to_business_client():
    client = RecordingBusinessClient()
    tool = TicketTool(client)

    result = asyncio.run(tool.create_ticket("u1001", "network", "宽带断网"))

    assert result["ticket_id"] == "TCK-TEST"
    assert client.calls == [
        ("create_ticket", {"user_id": "u1001", "issue_type": "network", "description": "宽带断网"})
    ]
