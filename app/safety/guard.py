from typing import Any

from app.safety.review_queue import ReviewQueue
from app.safety.risk_level import RiskLevel, SafetyAction, SafetyResult
from app.safety.rule_engine import RuleEngine
from app.safety.sanitizer import sanitize_text, sanitize_value


INPUT_BLOCKED_ANSWER = "输入包含高风险或敏感内容，已拦截并建议转人工客服。"
INPUT_REVIEW_ANSWER = "你的问题需要人工客服进一步确认，我会为你转接人工客服。"
OUTPUT_BLOCKED_ANSWER = "当前回答包含未经确认的高风险承诺或敏感内容，已转人工客服处理。"
TOOL_PARAM_BLOCKED_ANSWER = "工具调用参数包含高风险内容，已停止调用并建议转人工客服。"


class SafetyViolation(Exception):
    """内容安全拦截异常，统一由 CustomerAgent 转为结构化响应。"""

    def __init__(self, message: str, result: SafetyResult | None = None) -> None:
        super().__init__(message)
        self.result = result


class SafetyGuard:
    """内容安全门面。

    第 8 阶段把检测逻辑拆进 RuleEngine，但保留这个门面作为兼容入口，避免
    CustomerAgent 和旧测试直接依赖底层规则细节。
    """

    def __init__(self, rule_engine: RuleEngine | None = None, review_queue: ReviewQueue | None = None) -> None:
        self.rule_engine = rule_engine or RuleEngine()
        self.review_queue = review_queue or ReviewQueue()

    def check_input(self, message: str) -> None:
        result = self.scan_input(message)
        if result.action == SafetyAction.BLOCK:
            raise SafetyViolation(INPUT_BLOCKED_ANSWER, result)
        if result.action == SafetyAction.REVIEW:
            raise SafetyViolation(INPUT_REVIEW_ANSWER, result)

    def check_output(self, answer: str) -> None:
        result = self.scan_output(answer)
        if result.action != SafetyAction.ALLOW:
            raise SafetyViolation(OUTPUT_BLOCKED_ANSWER, result)

    def scan_input(self, message: str, *, trace_id: str = "") -> SafetyResult:
        result = self.rule_engine.scan(message, scope="input")
        result.review_queued = self._enqueue_if_needed(trace_id=trace_id, result=result, content=message)
        return result

    def scan_output(self, answer: str, *, trace_id: str = "") -> SafetyResult:
        result = self.rule_engine.scan(answer, scope="output")
        result.review_queued = self._enqueue_if_needed(trace_id=trace_id, result=result, content=answer)
        return result

    def scan_tool_params(self, params: dict[str, Any], *, trace_id: str = "") -> SafetyResult:
        content = _flatten_for_detection(params)
        result = self.rule_engine.scan(content, scope="tool")
        result.review_queued = self._enqueue_if_needed(trace_id=trace_id, result=result, content=content)
        return result

    def sanitize_tool_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return sanitize_value(payload)

    def sanitize_text(self, text: str) -> str:
        return sanitize_text(text)

    def _enqueue_if_needed(self, *, trace_id: str, result: SafetyResult, content: str) -> bool:
        if result.risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL}:
            return self.review_queue.enqueue(trace_id=trace_id, result=result, content=content)
        return False


def _flatten_for_detection(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key}:{_flatten_for_detection(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(_flatten_for_detection(item) for item in value)
    return str(value)
