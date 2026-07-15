import asyncio
from typing import Any

from app.tools.bill_tool import BillTool
from app.tools.business_client import BusinessClient
from app.tools.offer_tool import OfferTool
from app.tools.order_tool import OrderTool
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

    async def query_available_offers(self, user_id: str) -> dict[str, Any]:
        self.calls.append(("query_available_offers", {"user_id": user_id}))
        return {"offers": [{"offer_id": "OFF-DATA-20G", "name": "20GB 流量加油包优惠"}]}

    async def recommend_offers(
        self,
        user_id: str,
        need: str | None = None,
        budget: float | None = None,
    ) -> dict[str, Any]:
        self.calls.append(("recommend_offers", {"user_id": user_id, "need": need, "budget": budget}))
        return {"offers": [{"offer_id": "OFF-DATA-20G", "name": "20GB 流量加油包优惠"}]}

    async def query_order(self, user_id: str, order_id: str) -> dict[str, Any]:
        self.calls.append(("query_order", {"user_id": user_id, "order_id": order_id}))
        return {"order_id": order_id, "user_id": user_id, "status": "processing", "title": "测试订单"}

    async def query_recent_orders(self, user_id: str, limit: int = 3) -> dict[str, Any]:
        self.calls.append(("query_recent_orders", {"user_id": user_id, "limit": limit}))
        return {"orders": [{"order_id": "ORD-TEST", "user_id": user_id, "status": "processing"}]}


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


def test_offer_tool_delegates_to_business_client():
    client = RecordingBusinessClient()
    tool = OfferTool(client)

    result = asyncio.run(tool.recommend_offers("u1001", need="流量不够用", budget=20))

    assert result["offers"][0]["offer_id"] == "OFF-DATA-20G"
    assert client.calls == [("recommend_offers", {"user_id": "u1001", "need": "流量不够用", "budget": 20})]


def test_order_tool_delegates_to_business_client():
    client = RecordingBusinessClient()
    tool = OrderTool(client)

    result = asyncio.run(tool.query_order("u1001", "ORD-TEST"))

    assert result["order_id"] == "ORD-TEST"
    assert client.calls == [("query_order", {"user_id": "u1001", "order_id": "ORD-TEST"})]
