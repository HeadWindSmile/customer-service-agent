from copy import deepcopy
from uuid import uuid4


class MockBusinessClient:
    """模拟 Spring Boot 内部接口边界，AI 服务不直接操作业务数据库。"""

    def __init__(self) -> None:
        self._profiles = {
            "user_001": {"user_id": "user_001", "name": "演示用户", "level": "gold"},
            "u1001": {"user_id": "u1001", "name": "张先生", "level": "gold"},
            "u1002": {"user_id": "u1002", "name": "李女士", "level": "standard"},
        }
        self._packages = {
            "user_001": {"package_name": "5G畅享套餐", "monthly_fee": 129, "data_quota": "60GB"},
            "u1001": {"package_name": "5G畅享套餐", "monthly_fee": 129, "data_quota": "60GB"},
            "u1002": {"package_name": "基础套餐", "monthly_fee": 59, "data_quota": "20GB"},
        }
        self._bills = {
            ("user_001", "本月"): {"month": "本月", "amount": 156.8, "status": "已出账", "items": ["套餐月费", "流量包"]},
            ("u1001", "本月"): {"month": "本月", "amount": 156.8, "status": "已出账", "items": ["套餐月费", "流量包"]},
            ("u1002", "本月"): {"month": "本月", "amount": 68.0, "status": "已出账", "items": ["套餐月费", "语音通话"]},
        }

    def query_user_profile(self, user_id: str) -> dict:
        return deepcopy(self._profiles.get(user_id, {"user_id": user_id, "name": "模拟用户", "level": "standard"}))

    def query_user_package(self, user_id: str) -> dict:
        return deepcopy(
            self._packages.get(
                user_id,
                {"package_name": "基础套餐", "monthly_fee": 59, "data_quota": "20GB"},
            )
        )

    def query_bill(self, user_id: str, month: str) -> dict:
        bill = self._bills.get((user_id, month)) or self._bills.get((user_id, "本月"))
        if bill:
            return deepcopy(bill)
        return {"month": month, "amount": 0.0, "status": "暂无账单", "items": []}

    def change_package(self, user_id: str, target_package: str) -> dict:
        return {
            "order_id": f"PKG-{uuid4().hex[:10].upper()}",
            "user_id": user_id,
            "target_package": target_package,
            "status": "submitted",
        }

    def create_ticket(self, user_id: str, issue_type: str, description: str) -> dict:
        return {
            "ticket_id": f"TCK-{uuid4().hex[:10].upper()}",
            "user_id": user_id,
            "issue_type": issue_type,
            "description": description[:120],
            "status": "created",
        }

    def query_ticket(self, user_id: str, ticket_id: str) -> dict:
        """模拟售后系统工单查询接口，第四阶段只补 Router 场景闭环。"""

        return {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "status": "processing",
            "summary": "工单已受理，售后专员正在跟进。",
        }
