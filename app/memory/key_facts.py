import re
from typing import Any

from app.memory.privacy import sanitize_key_facts
from app.schemas.chat import ToolCall


_TICKET_RE = re.compile(r"TCK-[A-Za-z0-9]{6,}", re.IGNORECASE)
_MONTH_RE = re.compile(r"(20\d{2}[-年]?\d{1,2}|本月|上月)")
_KNOWN_PACKAGES = ["5G畅享套餐", "家庭融合套餐", "校园套餐", "基础套餐"]


class KeyFactsExtractor:
    """从多轮信息里提取少量安全事实。

    key_facts 不是用户画像系统，只服务当前会话的指代消解；因此采用白名单和覆盖更新，
    只记“刚才说的套餐/账单月份/工单号”等客服上下文。
    """

    def merge(
        self,
        existing: dict[str, Any],
        user_message: str,
        assistant_answer: str,
        slots: dict[str, Any],
        tool_calls: list[ToolCall],
    ) -> dict[str, Any]:
        facts = dict(existing)
        facts.update(self._from_text(user_message))
        facts.update(self._from_text(assistant_answer))
        facts.update(self._from_slots(slots))
        facts.update(self._from_tool_calls(tool_calls))
        return sanitize_key_facts(facts)

    def _from_slots(self, slots: dict[str, Any]) -> dict[str, Any]:
        facts: dict[str, Any] = {}
        if slots.get("target_package"):
            facts["target_package"] = slots["target_package"]
        if slots.get("product_name"):
            facts["last_product_name"] = slots["product_name"]
        if slots.get("month"):
            facts["last_bill_month"] = str(slots["month"]).replace("年", "-")
        if slots.get("ticket_id"):
            facts["last_ticket_id"] = str(slots["ticket_id"]).upper()
        if slots.get("issue_type"):
            facts["last_issue_type"] = slots["issue_type"]
        return facts

    def _from_tool_calls(self, tool_calls: list[ToolCall]) -> dict[str, Any]:
        facts: dict[str, Any] = {}
        for call in tool_calls:
            output = call.output or {}
            if call.tool_name == "query_user_package" and output.get("package_name"):
                facts["current_package"] = output["package_name"]
            if call.tool_name == "change_package" and output.get("target_package"):
                facts["target_package"] = output["target_package"]
            if call.tool_name == "query_bill" and output.get("month"):
                facts["last_bill_month"] = output["month"]
            if call.tool_name in {"create_ticket", "query_ticket"} and output.get("ticket_id"):
                facts["last_ticket_id"] = str(output["ticket_id"]).upper()
            if output.get("issue_type"):
                facts["last_issue_type"] = output["issue_type"]
        return facts

    def _from_text(self, text: str) -> dict[str, Any]:
        facts: dict[str, Any] = {}
        ticket_match = _TICKET_RE.search(text)
        if ticket_match:
            facts["last_ticket_id"] = ticket_match.group(0).upper()
        month_match = _MONTH_RE.search(text)
        if month_match and any(word in text for word in ["账单", "话费", "费用", "扣费"]):
            facts["last_bill_month"] = month_match.group(1).replace("年", "-")
        for package in _KNOWN_PACKAGES:
            if package in text:
                facts["target_package"] = package
                facts["last_product_name"] = package
                break
        if any(word in text for word in ["宽带", "断网", "不能上网", "连不上", "没信号"]):
            facts["last_issue_type"] = "network"
        return facts

