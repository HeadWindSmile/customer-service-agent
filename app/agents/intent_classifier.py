import re
from typing import Any

from app.agents.chains.intent_chain import IntentChain
from app.agents.intent_schema import IntentName
from app.config import settings
from app.observability.logger import log_event
from app.schemas.chat import IntentResult


class IntentClassifier:
    """两阶段意图识别：规则预分类 + LLM 结构化识别。

    规则层先覆盖高确定性客服场景，保证本地 demo 和核心链路稳定；低确定性问题
    再交给 LLM 输出 JSON。真实模型不可用时 fallback 到规则结果，避免外部依赖拖垮服务。
    """

    _month_pattern = re.compile(r"(20\d{2}[-年]?\d{1,2}|本月|上月)")
    _target_user_pattern = re.compile(r"(?:用户|客户)?\s*([uU]\d{3,}|user[_-]?\d+)")
    _ticket_pattern = re.compile(r"(TCK-[A-Za-z0-9]{6,}|工单[号：:\s]*([A-Za-z0-9-]{6,}))", re.IGNORECASE)
    _order_pattern = re.compile(r"((?:ORD|PKG)-[A-Za-z0-9]{6,})", re.IGNORECASE)
    _phone_pattern = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
    _budget_pattern = re.compile(r"(?:预算|不超过|以内|每月)?\s*(\d+(?:\.\d+)?)\s*元")

    def __init__(self, intent_chain: IntentChain | None = None) -> None:
        self.intent_chain = intent_chain or IntentChain()

    def classify(self, message: str) -> IntentResult:
        text = message.strip()
        rule_result = self._classify_by_rules(text)
        if (
            rule_result.intent != IntentName.UNKNOWN.value
            and rule_result.confidence >= settings.intent_rule_direct_threshold
        ):
            return rule_result

        try:
            llm_result = self.intent_chain.classify(
                message=text,
                rule_intent=rule_result.intent,
                rule_confidence=rule_result.confidence,
                rule_slots=rule_result.slots,
                rule_reason=rule_result.reason,
            )
            merged_slots = {**rule_result.slots, **llm_result.slots}
            return IntentResult(
                intent=str(llm_result.intent),
                slots=merged_slots,
                confidence=llm_result.confidence,
                reason=llm_result.reason or "LLM 结构化意图识别",
            )
        except Exception as exc:
            log_event(
                "intent.llm_fallback_to_rule",
                {
                    "rule_intent": rule_result.intent,
                    "rule_confidence": rule_result.confidence,
                    "error": str(exc),
                },
                level="error",
            )
            return rule_result

    def _classify_by_rules(self, text: str) -> IntentResult:
        slots: dict[str, Any] = {}
        self._fill_common_slots(text, slots)

        if self._is_human_transfer(text):
            return self._result(IntentName.HUMAN_TRANSFER, slots, 0.94, "命中转人工关键词")

        if self._is_ticket_query(text):
            slots.setdefault("ticket_id", self._extract_ticket_id(text))
            return self._result(IntentName.TICKET_QUERY, slots, 0.9, "命中工单查询关键词")

        if self._is_order_query(text):
            order_id = self._extract_order_id(text)
            if order_id:
                slots.setdefault("order_id", order_id)
            return self._result(IntentName.ORDER_QUERY, slots, 0.9, "命中订单查询关键词")

        if self._is_network_repair(text):
            slots.setdefault("issue_type", "network")
            return self._result(IntentName.NETWORK_REPAIR, slots, 0.9, "命中网络报修关键词")

        if self._is_ticket_create(text):
            slots.setdefault("issue_type", self._extract_issue_type(text))
            return self._result(IntentName.TICKET_CREATE, slots, 0.89, "命中工单创建关键词")

        if self._is_package_change(text):
            slots.setdefault("target_package", self._extract_target_package(text))
            return self._result(IntentName.PACKAGE_CHANGE, slots, 0.92, "命中套餐办理/变更关键词")

        if self._is_offer_recommend(text):
            slots.setdefault("need", self._extract_offer_need(text))
            budget = self._extract_budget(text)
            if budget is not None:
                slots.setdefault("budget", budget)
            return self._result(IntentName.OFFER_RECOMMEND, slots, 0.9, "命中优惠推荐关键词")

        if self._is_offer_query(text):
            slots.setdefault("offer_type", self._extract_offer_type(text))
            return self._result(IntentName.OFFER_QUERY, slots, 0.89, "命中优惠/权益查询关键词")

        if self._is_package_recommend(text):
            slots.setdefault("product_name", "套餐")
            return self._result(IntentName.PACKAGE_RECOMMEND, slots, 0.88, "命中套餐推荐关键词")

        if self._contains(text, ["当前套餐", "我的套餐", "套餐信息", "查套餐", "套餐查询"]):
            return self._result(IntentName.PACKAGE_QUERY, slots, 0.91, "命中套餐查询关键词")

        if self._is_bill_explain(text):
            slots.setdefault("month", self._extract_month(text))
            return self._result(IntentName.BILL_EXPLAIN, slots, 0.88, "命中账单解释关键词")

        if self._is_bill_query(text):
            slots.setdefault("month", self._extract_month(text))
            return self._result(IntentName.BILL_QUERY, slots, 0.9, "命中账单查询关键词")

        if self._is_fault_diagnosis(text):
            slots.setdefault("issue_type", self._extract_issue_type(text))
            return self._result(IntentName.FAULT_DIAGNOSIS, slots, 0.87, "命中故障排查关键词")

        if self._is_package_faq(text):
            return self._result(IntentName.FAQ_QUERY, slots, 0.88, "命中套餐规则咨询关键词")

        if self._contains(text, ["规则", "政策", "说明", "介绍", "是什么", "什么时候", "怎么办", "如何"]):
            return self._result(IntentName.FAQ_QUERY, slots, 0.74, "命中通用知识库咨询关键词")

        return self._result(IntentName.UNKNOWN, slots, 0.35, "规则无法确定意图")

    def _result(self, intent: IntentName, slots: dict[str, Any], confidence: float, reason: str) -> IntentResult:
        return IntentResult(intent=intent.value, slots=slots, confidence=confidence, reason=reason)

    def _fill_common_slots(self, text: str, slots: dict[str, Any]) -> None:
        user_match = self._target_user_pattern.search(text)
        if user_match:
            slots["target_user_id"] = user_match.group(1).lower()

        phone_match = self._phone_pattern.search(text)
        if phone_match:
            phone = phone_match.group(1)
            slots["phone_number"] = f"{phone[:3]}****{phone[-4:]}"

        ticket_id = self._extract_ticket_id(text)
        if ticket_id:
            slots["ticket_id"] = ticket_id

        order_id = self._extract_order_id(text)
        if order_id:
            slots["order_id"] = order_id

    def _extract_month(self, text: str) -> str:
        match = self._month_pattern.search(text)
        return match.group(1).replace("年", "-") if match else "本月"

    def _extract_target_package(self, text: str) -> str:
        packages = ["5G畅享套餐", "家庭融合套餐", "校园套餐", "基础套餐"]
        for package in packages:
            if package in text:
                return package
        return "5G畅享套餐"

    def _extract_issue_type(self, text: str) -> str:
        if self._contains(text, ["宽带", "断网", "不能上网", "网络", "连不上", "没信号"]):
            return "network"
        if self._contains(text, ["账单", "扣费", "话费"]):
            return "billing"
        if self._contains(text, ["套餐"]):
            return "package"
        return "general"

    def _extract_ticket_id(self, text: str) -> str:
        match = self._ticket_pattern.search(text)
        if not match:
            return ""
        return (match.group(2) or match.group(1)).upper().replace("工单", "").strip(" ：:")

    def _extract_order_id(self, text: str) -> str:
        match = self._order_pattern.search(text)
        return match.group(1).upper() if match else ""

    def _extract_budget(self, text: str) -> float | None:
        match = self._budget_pattern.search(text)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def _extract_offer_type(self, text: str) -> str:
        if self._contains(text, ["流量", "加油包", "不够用"]):
            return "data_booster"
        if self._contains(text, ["会员", "权益", "视频"]):
            return "member_benefit"
        if self._contains(text, ["家庭", "宽带", "融合"]):
            return "family_bundle"
        return "general"

    def _extract_offer_need(self, text: str) -> str:
        if self._contains(text, ["流量", "加油包", "不够用"]):
            return "流量不够用"
        if self._contains(text, ["会员", "权益", "视频"]):
            return "会员权益"
        if self._contains(text, ["家庭", "宽带", "融合"]):
            return "家庭宽带融合"
        return "优惠权益"

    def _contains(self, text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    def _is_human_transfer(self, text: str) -> bool:
        return self._contains(text, ["转人工", "人工客服", "真人客服", "人工处理", "找客服"])

    def _is_ticket_query(self, text: str) -> bool:
        if not self._contains(text, ["工单", "TCK-", "报修单"]):
            return False
        return self._contains(text, ["查询", "查", "进度", "状态", "到哪", "处理到", "怎么样"])

    def _is_order_query(self, text: str) -> bool:
        if self._extract_order_id(text):
            return self._contains(text, ["订单", "状态", "进度", "查", "查询", "办理", "申请"]) or "ORD-" in text.upper()
        if not self._contains(text, ["订单", "业务单", "申请单", "办理进度"]):
            return False
        return self._contains(text, ["查询", "查", "进度", "状态", "到哪", "处理到", "最近", "我的"])

    def _is_network_repair(self, text: str) -> bool:
        return self._contains(text, ["报修", "上门维修", "网络修复", "宽带维修"]) and self._contains(
            text,
            ["宽带", "网络", "断网", "连不上", "没信号"],
        )

    def _is_ticket_create(self, text: str) -> bool:
        if self._is_ticket_query(text):
            return False
        if self._contains(text, ["创建工单", "新建工单", "提交工单", "售后工单", "投诉"]):
            return True
        return "工单" in text and self._contains(text, ["创建", "新建", "提交", "帮我"])

    def _is_package_change(self, text: str) -> bool:
        if self._is_package_faq(text):
            return False

        direct_keywords = ["改套餐", "变更套餐", "升级套餐", "降级套餐", "办理套餐", "换套餐", "套餐改成"]
        if self._contains(text, direct_keywords):
            return True
        if self._contains(text, ["改成", "变成", "调整为", "切换到"]) and self._contains(text, ["套餐", "5G畅享"]):
            return True
        return self._contains(text, ["办理", "开通", "申请"]) and self._contains(
            text,
            ["套餐", "5G畅享", "家庭融合", "校园套餐", "基础套餐"],
        )

    def _is_package_recommend(self, text: str) -> bool:
        if not self._contains(text, ["套餐", "流量", "资费"]):
            return False
        return self._contains(text, ["推荐", "适合", "哪个更好", "怎么选", "不够用", "性价比", "划算"])

    def _is_offer_recommend(self, text: str) -> bool:
        if not self._contains(text, ["优惠", "权益", "活动", "offer", "流量包", "加油包", "会员"]):
            return False
        return self._contains(text, ["推荐", "适合", "怎么选", "不够用", "划算", "预算", "想要"])

    def _is_offer_query(self, text: str) -> bool:
        if not self._contains(text, ["优惠", "权益", "活动", "offer", "流量包", "加油包", "会员"]):
            return False
        return self._contains(text, ["查询", "查", "可办理", "有什么", "有哪些", "能办", "能领", "推荐"])

    def _is_package_faq(self, text: str) -> bool:
        if not self._contains(text, ["套餐", "5G畅享", "家庭融合", "校园套餐", "基础套餐"]):
            return False
        return self._contains(
            text,
            ["规则", "政策", "说明", "介绍", "是什么", "什么时候", "怎么收费", "多少钱", "能退", "退订", "生效"],
        )

    def _is_bill_query(self, text: str) -> bool:
        if self._is_bill_explain(text):
            return False
        return self._contains(text, ["账单", "话费", "扣费", "欠费", "消费明细", "余额"])

    def _is_bill_explain(self, text: str) -> bool:
        if not self._contains(text, ["账单", "话费", "扣费", "费用", "超量", "流量费"]):
            return False
        return self._contains(text, ["为什么", "原因", "规则", "说明", "组成", "是什么", "怎么算", "解释", "明细"])

    def _is_fault_diagnosis(self, text: str) -> bool:
        return self._contains(text, ["不能上网", "断网", "没信号", "故障", "宽带慢", "网络慢", "无法连接", "连不上"])
