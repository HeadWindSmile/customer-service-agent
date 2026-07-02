from abc import ABC, abstractmethod

from app.safety.risk_level import RiskLevel, SafetyFinding
from app.safety.sanitizer import sanitize_text


class BaseSemanticDetector(ABC):
    """语义检测接口。

    第 8 阶段只用 mock 启发式实现，保留接口是为了后续可替换为真实 LLM 安全审核
    或企业内容安全服务，而不影响 RuleEngine 和 CustomerAgent。
    """

    @abstractmethod
    def detect(self, text: str, *, scope: str) -> list[SafetyFinding]:
        raise NotImplementedError


class MockSemanticDetector(BaseSemanticDetector):
    """本地 mock 语义检测。

    这里不调用真实模型，只识别企业客服场景中常见的语义风险：越狱诱导、索取隐私、
    违规操作、辱骂攻击和输出高危承诺。
    """

    def detect(self, text: str, *, scope: str) -> list[SafetyFinding]:
        normalized = text.lower()
        findings: list[SafetyFinding] = []
        if _contains_any(normalized, ["忽略之前", "无视之前", "系统提示词", "隐藏规则", "developer message", "system prompt"]):
            findings.append(_finding("prompt_injection", RiskLevel.HIGH, "semantic_prompt_injection", "检测到提示词注入或系统提示词探测。", text))
        if _contains_any(normalized, ["越狱", "jailbreak", "dan模式", "不受限制", "绕过安全"]):
            findings.append(_finding("jailbreak", RiskLevel.HIGH, "semantic_jailbreak", "检测到越狱诱导。", text))
        if _contains_any(text, ["身份证", "银行卡", "验证码", "密码", "内部系统"]) and _contains_any(text, ["告诉我", "泄露", "导出", "查看", "查询", "给我"]):
            findings.append(_finding("privacy_leak", RiskLevel.HIGH, "semantic_privacy_request", "检测到索取隐私或内部敏感信息。", text))
        if _contains_any(text, ["攻击", "盗取", "破解", "钓鱼", "木马", "撞库"]):
            findings.append(_finding("illegal_request", RiskLevel.CRITICAL, "semantic_illegal_request", "检测到违法违规请求。", text))
        if _contains_any(text, ["垃圾客服", "傻逼", "去死", "废物"]) and scope == "input":
            findings.append(_finding("abuse", RiskLevel.MEDIUM, "semantic_abuse", "检测到辱骂或攻击性表达，建议转人工安抚。", text))
        if scope == "output" and _contains_any(text, ["保证赔偿", "一定免费", "绝对不会", "内部数据", "百分百解决"]):
            findings.append(_finding("price_commitment", RiskLevel.HIGH, "semantic_output_commitment", "检测到未经确认的高危服务承诺。", text))
        return findings


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _finding(risk_type: str, risk_level: RiskLevel, rule_id: str, message: str, evidence: str) -> SafetyFinding:
    return SafetyFinding(
        risk_type=risk_type,
        risk_level=risk_level,
        source="semantic_mock",
        rule_id=rule_id,
        message=message,
        evidence_masked=sanitize_text(evidence[:120]),
    )
