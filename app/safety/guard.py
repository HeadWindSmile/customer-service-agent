from app.config import settings


class SafetyViolation(Exception):
    """内容安全拦截异常，统一由 CustomerAgent 转为结构化响应。"""


class SafetyGuard:
    """第一阶段实现最小安全防护，先阻断明显风险输入和高危输出承诺。"""

    def check_input(self, message: str) -> None:
        for word in settings.safety_blocked_words:
            if word and word in message:
                raise SafetyViolation("输入包含敏感或越权内容，已拦截并建议转人工客服。")

    def check_output(self, answer: str) -> None:
        for phrase in settings.output_forbidden_phrases:
            if phrase and phrase in answer:
                raise SafetyViolation("输出命中高风险承诺，已拦截并建议转人工客服。")

