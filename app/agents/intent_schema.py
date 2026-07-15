from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IntentName(str, Enum):
    """集中维护 intent 枚举，避免规则、LLM prompt 和 Router 各自写一份字符串。"""

    FAQ_QUERY = "faq_query"
    PACKAGE_QUERY = "package_query"
    PACKAGE_RECOMMEND = "package_recommend"
    PACKAGE_CHANGE = "package_change"
    BILL_QUERY = "bill_query"
    BILL_EXPLAIN = "bill_explain"
    FAULT_DIAGNOSIS = "fault_diagnosis"
    NETWORK_REPAIR = "network_repair"
    TICKET_CREATE = "ticket_create"
    TICKET_QUERY = "ticket_query"
    OFFER_QUERY = "offer_query"
    OFFER_RECOMMEND = "offer_recommend"
    ORDER_QUERY = "order_query"
    HUMAN_TRANSFER = "human_transfer"
    UNKNOWN = "unknown"


INTENT_DESCRIPTIONS: dict[str, str] = {
    IntentName.FAQ_QUERY.value: "知识库咨询、规则政策、办理说明等通用问答。",
    IntentName.PACKAGE_QUERY.value: "查询用户当前套餐、套餐余量或套餐基础信息。",
    IntentName.PACKAGE_RECOMMEND.value: "根据用户诉求推荐或比较套餐，不直接办理。",
    IntentName.PACKAGE_CHANGE.value: "用户明确要求办理、升级、降级或变更套餐。",
    IntentName.BILL_QUERY.value: "查询账单金额、账单状态、消费明细等业务数据。",
    IntentName.BILL_EXPLAIN.value: "解释账单组成、扣费原因、超量费用规则。",
    IntentName.FAULT_DIAGNOSIS.value: "用户询问网络、宽带、信号等故障如何排查。",
    IntentName.NETWORK_REPAIR.value: "用户明确要求报修、上门维修或网络修复。",
    IntentName.TICKET_CREATE.value: "创建售后、投诉、故障等工单。",
    IntentName.TICKET_QUERY.value: "查询已有工单进度或状态。",
    IntentName.OFFER_QUERY.value: "查询用户可办理优惠、权益、活动或可领取 offer。",
    IntentName.OFFER_RECOMMEND.value: "根据用户流量、权益、预算等诉求推荐合适 offer。",
    IntentName.ORDER_QUERY.value: "查询订单状态、办理进度、最近订单或指定订单详情。",
    IntentName.HUMAN_TRANSFER.value: "用户要求人工客服、真人客服或无法自助处理。",
    IntentName.UNKNOWN.value: "无法判断用户意图，或问题与客服业务无关。",
}

SLOT_DESCRIPTIONS: dict[str, str] = {
    "month": "账单月份，例如 本月、上月、2026-06。",
    "target_package": "用户想办理或咨询的目标套餐名称。",
    "issue_type": "问题类型，例如 network、billing、package、general。",
    "ticket_id": "售后工单号。",
    "order_id": "业务订单号，例如 ORD-20260701001 或 PKG-20260630001。",
    "offer_type": "优惠权益类型，例如 data_booster、member_benefit、family_bundle。",
    "need": "用户诉求，例如流量不够、想要会员权益、家庭宽带共享。",
    "budget": "用户可接受的月增费用，单位元。",
    "phone_number": "脱敏后的手机号。",
    "product_name": "用户提到的业务产品名称。",
    "target_user_id": "客服代查或文本中提到的目标用户 ID。",
}

SUPPORTED_INTENTS = {intent.value for intent in IntentName}


class StructuredIntentResult(BaseModel):
    """LLM 和规则分类器共同使用的结构化结果。

    这里保留 reason 是为了面试讲解和 trace 排障：当路由错了，可以看到模型或规则
    为什么把问题归到某一类，而不只是一段不可解释的文本。
    """

    model_config = ConfigDict(use_enum_values=True)

    intent: IntentName
    slots: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""

    @field_validator("slots")
    @classmethod
    def normalize_slot_keys(cls, value: dict[str, Any]) -> dict[str, Any]:
        return {str(key): slot_value for key, slot_value in value.items() if slot_value not in (None, "")}


def normalize_intent_name(intent: str) -> str:
    """把外部模型可能输出的未知标签收敛到 unknown，保护 Router 不被任意字符串污染。"""

    normalized = intent.strip().lower()
    return normalized if normalized in SUPPORTED_INTENTS else IntentName.UNKNOWN.value
