from copy import deepcopy
from uuid import uuid4


# 这些数据刻意放在 mock_business_service 内部，表示它们属于“业务系统”。
# AI 服务只能通过 HTTP client 访问这些能力，不能直接读取这里的数据结构。
USERS: dict[str, dict] = {
    "user_001": {"user_id": "user_001", "name": "演示用户", "level": "gold"},
    "u1001": {"user_id": "u1001", "name": "张先生", "level": "gold"},
    "u1002": {"user_id": "u1002", "name": "李女士", "level": "standard"},
}

AVAILABLE_PACKAGES: dict[str, dict] = {
    "5G畅享套餐": {"package_name": "5G畅享套餐", "monthly_fee": 129, "data_quota": "60GB"},
    "基础套餐": {"package_name": "基础套餐", "monthly_fee": 59, "data_quota": "20GB"},
    "家庭融合套餐": {"package_name": "家庭融合套餐", "monthly_fee": 199, "data_quota": "100GB"},
    "校园套餐": {"package_name": "校园套餐", "monthly_fee": 39, "data_quota": "30GB"},
}

USER_PACKAGES: dict[str, dict] = {
    "user_001": deepcopy(AVAILABLE_PACKAGES["5G畅享套餐"]),
    "u1001": deepcopy(AVAILABLE_PACKAGES["5G畅享套餐"]),
    "u1002": deepcopy(AVAILABLE_PACKAGES["基础套餐"]),
}

BILLS: dict[tuple[str, str], dict] = {
    ("user_001", "本月"): {
        "month": "本月",
        "amount": 156.8,
        "status": "已出账",
        "items": ["套餐月费", "流量包"],
    },
    ("u1001", "本月"): {
        "month": "本月",
        "amount": 156.8,
        "status": "已出账",
        "items": ["套餐月费", "流量包"],
    },
    ("u1002", "本月"): {
        "month": "本月",
        "amount": 68.0,
        "status": "已出账",
        "items": ["套餐月费", "语音通话"],
    },
    ("u1001", "2025-04"): {
        "month": "2025-04",
        "amount": 142.5,
        "status": "已出账",
        "items": ["套餐月费", "增值业务"],
    },
}

TICKETS: dict[str, dict] = {
    "TCK-ABC123456": {
        "ticket_id": "TCK-ABC123456",
        "user_id": "user_001",
        "issue_type": "network",
        "description": "历史演示工单",
        "status": "processing",
        "summary": "工单已受理，售后专员正在跟进。",
    }
}


def get_user(user_id: str) -> dict | None:
    user = USERS.get(user_id)
    return deepcopy(user) if user else None


def get_user_package(user_id: str) -> dict | None:
    package = USER_PACKAGES.get(user_id)
    return deepcopy(package) if package else None


def get_bill(user_id: str, month: str) -> dict | None:
    bill = BILLS.get((user_id, month))
    return deepcopy(bill) if bill else None


def change_user_package(user_id: str, target_package: str) -> dict:
    package = deepcopy(AVAILABLE_PACKAGES[target_package])
    USER_PACKAGES[user_id] = package
    return {
        "order_id": f"PKG-{uuid4().hex[:10].upper()}",
        "user_id": user_id,
        "target_package": target_package,
        "status": "submitted",
    }


def create_ticket(user_id: str, issue_type: str, description: str) -> dict:
    ticket_id = f"TCK-{uuid4().hex[:10].upper()}"
    ticket = {
        "ticket_id": ticket_id,
        "user_id": user_id,
        "issue_type": issue_type,
        "description": description[:120],
        "status": "created",
        "summary": "工单已创建，等待售后专员处理。",
    }
    TICKETS[ticket_id] = ticket
    return deepcopy(ticket)


def get_ticket(ticket_id: str) -> dict | None:
    ticket = TICKETS.get(ticket_id)
    return deepcopy(ticket) if ticket else None
