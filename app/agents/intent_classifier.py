import re

from app.schemas.chat import IntentResult


class IntentClassifier:
    """第一阶段使用规则分类，先稳定工程链路，后续再替换为 LLM 结构化识别。"""

    _month_pattern = re.compile(r"(20\d{2}[-年]?\d{1,2}|本月|上月)")
    _target_user_pattern = re.compile(r"(?:用户|客户)?\s*([uU]\d{3,}|user[_-]?\d+)")

    def classify(self, message: str) -> IntentResult:
        text = message.strip()
        slots: dict[str, str] = {}
        self._fill_common_slots(text, slots)

        if self._is_package_change(text):
            slots.setdefault("target_package", self._extract_target_package(text))
            return IntentResult(intent="package_change", slots=slots, confidence=0.9)

        if self._contains(text, ["当前套餐", "我的套餐", "套餐信息", "查套餐", "套餐查询"]):
            return IntentResult(intent="package_query", slots=slots, confidence=0.9)

        if self._contains(text, ["账单", "话费", "扣费", "欠费", "消费明细"]):
            slots.setdefault("month", self._extract_month(text))
            return IntentResult(intent="bill_query", slots=slots, confidence=0.88)

        if self._contains(text, ["创建工单", "报修", "投诉", "售后工单", "转人工"]):
            slots.setdefault("issue_type", self._extract_issue_type(text))
            return IntentResult(intent="ticket_create", slots=slots, confidence=0.86)

        if self._contains(text, ["不能上网", "断网", "没信号", "故障", "宽带慢", "网络慢", "无法连接"]):
            slots.setdefault("issue_type", self._extract_issue_type(text))
            return IntentResult(intent="fault_diagnosis", slots=slots, confidence=0.84)

        return IntentResult(intent="faq_query", slots=slots, confidence=0.72)

    def _fill_common_slots(self, text: str, slots: dict[str, str]) -> None:
        user_match = self._target_user_pattern.search(text)
        if user_match:
            slots["target_user_id"] = user_match.group(1).lower()

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
        if self._contains(text, ["宽带", "断网", "不能上网", "网络"]):
            return "network"
        if self._contains(text, ["账单", "扣费", "话费"]):
            return "billing"
        if self._contains(text, ["套餐"]):
            return "package"
        return "general"

    def _contains(self, text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    def _is_package_change(self, text: str) -> bool:
        direct_keywords = ["改套餐", "变更套餐", "升级套餐", "降级套餐", "办理套餐", "换套餐"]
        if self._contains(text, direct_keywords):
            return True
        return self._contains(text, ["办理", "开通", "申请"]) and self._contains(
            text,
            ["套餐", "5G畅享", "家庭融合", "校园套餐", "基础套餐"],
        )
