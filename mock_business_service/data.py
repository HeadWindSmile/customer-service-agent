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

OFFERS: dict[str, dict] = {
    "OFF-DATA-20G": {
        "offer_id": "OFF-DATA-20G",
        "name": "20GB 流量加油包优惠",
        "offer_type": "data_booster",
        "description": "适合本月流量经常不够用的用户，办理后立即生效。",
        "benefits": ["每月额外 20GB 国内通用流量", "首月按天折算"],
        "monthly_fee_delta": 19.0,
        "valid_until": "2026-12-31",
        "eligible_levels": ["gold", "standard"],
        "applicable_packages": ["5G畅享套餐", "基础套餐"],
        "tags": ["流量", "data", "高性价比"],
        "recommend_reason": "匹配流量不够用诉求，月增费用较低。",
    },
    "OFF-MEMBER-VIDEO": {
        "offer_id": "OFF-MEMBER-VIDEO",
        "name": "视频会员权益包",
        "offer_type": "member_benefit",
        "description": "面向金卡用户开放的视频会员权益优惠。",
        "benefits": ["月度视频会员权益", "权益到期前短信提醒"],
        "monthly_fee_delta": 15.0,
        "valid_until": "2026-10-31",
        "eligible_levels": ["gold"],
        "applicable_packages": ["5G畅享套餐", "家庭融合套餐"],
        "tags": ["权益", "会员", "video"],
        "recommend_reason": "匹配权益类诉求，当前用户等级可办理。",
    },
    "OFF-FAMILY-BUNDLE": {
        "offer_id": "OFF-FAMILY-BUNDLE",
        "name": "家庭融合权益升级",
        "offer_type": "family_bundle",
        "description": "适合多成员共享流量和宽带权益的家庭用户。",
        "benefits": ["家庭成员共享流量池", "宽带提速权益"],
        "monthly_fee_delta": 39.0,
        "valid_until": "2026-09-30",
        "eligible_levels": ["gold"],
        "applicable_packages": ["家庭融合套餐", "5G畅享套餐"],
        "tags": ["家庭", "宽带", "融合"],
        "recommend_reason": "匹配家庭共享和宽带权益诉求。",
    },
}

ORDERS: dict[str, dict] = {
    "ORD-20260701001": {
        "order_id": "ORD-20260701001",
        "user_id": "u1001",
        "order_type": "offer_subscribe",
        "title": "20GB 流量加油包优惠办理",
        "status": "processing",
        "created_at": "2026-07-01T10:15:00+08:00",
        "updated_at": "2026-07-01T10:20:00+08:00",
        "related_resource_id": "OFF-DATA-20G",
        "can_cancel": True,
        "summary": "订单已受理，权益预计 10 分钟内生效。",
    },
    "PKG-20260630001": {
        "order_id": "PKG-20260630001",
        "user_id": "u1001",
        "order_type": "package_change",
        "title": "5G畅享套餐变更",
        "status": "completed",
        "created_at": "2026-06-30T18:30:00+08:00",
        "updated_at": "2026-07-01T00:05:00+08:00",
        "related_resource_id": "5G畅享套餐",
        "can_cancel": False,
        "summary": "套餐变更已完成，当前套餐为 5G畅享套餐。",
    },
    "ORD-20260702002": {
        "order_id": "ORD-20260702002",
        "user_id": "u1002",
        "order_type": "ticket_service",
        "title": "宽带售后服务单",
        "status": "processing",
        "created_at": "2026-07-02T09:00:00+08:00",
        "updated_at": "2026-07-02T11:30:00+08:00",
        "related_resource_id": "TCK-ABC123456",
        "can_cancel": False,
        "summary": "售后专员正在跟进，预计 24 小时内反馈。",
    },
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
    order_id = f"PKG-{uuid4().hex[:10].upper()}"
    ORDERS[order_id] = {
        "order_id": order_id,
        "user_id": user_id,
        "order_type": "package_change",
        "title": f"{target_package} 变更申请",
        "status": "submitted",
        "created_at": "2026-07-04T12:00:00+08:00",
        "updated_at": "2026-07-04T12:00:00+08:00",
        "related_resource_id": target_package,
        "can_cancel": True,
        "summary": "套餐变更申请已提交，生效时间以业务系统确认为准。",
    }
    return {
        "order_id": order_id,
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


def get_available_offers(user_id: str) -> list[dict]:
    user = USERS.get(user_id)
    package = USER_PACKAGES.get(user_id)
    if not user or not package:
        return []
    user_level = user.get("level", "")
    package_name = package.get("package_name", "")
    offers = []
    for offer in OFFERS.values():
        if user_level not in offer.get("eligible_levels", []):
            continue
        if package_name not in offer.get("applicable_packages", []):
            continue
        offers.append(_public_offer(offer))
    return offers


def recommend_offers(user_id: str, need: str | None = None, budget: float | None = None) -> list[dict]:
    offers = get_available_offers(user_id)
    need_text = (need or "").strip().lower()
    if budget is not None:
        offers = [offer for offer in offers if float(offer["monthly_fee_delta"]) <= budget]
    if not need_text:
        return offers[:3]

    scored: list[tuple[int, dict]] = []
    for offer in offers:
        text = " ".join([offer["name"], offer["description"], " ".join(offer.get("tags", []))]).lower()
        score = sum(1 for token in _need_tokens(need_text) if token and token.lower() in text)
        scored.append((score, offer))
    matched = [offer for score, offer in sorted(scored, key=lambda item: item[0], reverse=True) if score > 0]
    return (matched or offers)[:3]


def get_order(user_id: str, order_id: str) -> dict | None:
    order = ORDERS.get(order_id.upper())
    if not order or order.get("user_id") != user_id:
        return None
    return deepcopy(order)


def get_recent_orders(user_id: str, limit: int = 3) -> list[dict]:
    orders = [deepcopy(order) for order in ORDERS.values() if order.get("user_id") == user_id]
    orders.sort(key=lambda order: order.get("created_at", ""), reverse=True)
    return orders[: max(1, limit)]


def _public_offer(offer: dict) -> dict:
    public_fields = {
        "offer_id",
        "name",
        "offer_type",
        "description",
        "benefits",
        "monthly_fee_delta",
        "valid_until",
        "tags",
        "recommend_reason",
    }
    return {key: deepcopy(value) for key, value in offer.items() if key in public_fields}


def _need_tokens(need_text: str) -> list[str]:
    tokens = [need_text]
    if "流量" in need_text or "data" in need_text or "不够" in need_text:
        tokens.extend(["流量", "data"])
    if "会员" in need_text or "权益" in need_text or "视频" in need_text:
        tokens.extend(["会员", "权益", "video"])
    if "家庭" in need_text or "宽带" in need_text or "融合" in need_text:
        tokens.extend(["家庭", "宽带", "融合"])
    return tokens
