import re
from dataclasses import dataclass
from re import Pattern

from app.safety.risk_level import RiskLevel, SafetyFinding
from app.safety.sanitizer import sanitize_text


@dataclass(frozen=True)
class RegexRule:
    rule_id: str
    risk_type: str
    risk_level: RiskLevel
    pattern: Pattern[str]
    message: str
    scopes: tuple[str, ...] = ("input", "output", "tool")


class RegexDetector:
    """正则检测器负责稳定识别格式化风险。

    手机号、身份证、银行卡、邮箱、API Key 这类内容用正则比关键词更可靠；
    同时它只产出结构化 finding，不直接决定拦截动作，动作统一交给 RuleEngine。
    """

    def __init__(self, rules: list[RegexRule] | None = None) -> None:
        self.rules = rules or _default_regex_rules()

    def detect(self, text: str, *, scope: str) -> list[SafetyFinding]:
        findings: list[SafetyFinding] = []
        for rule in self.rules:
            if scope not in rule.scopes and "all" not in rule.scopes:
                continue
            for match in rule.pattern.finditer(text):
                evidence = match.group(0)
                findings.append(
                    SafetyFinding(
                        risk_type=rule.risk_type,
                        risk_level=rule.risk_level,
                        source="regex",
                        rule_id=rule.rule_id,
                        message=rule.message,
                        evidence_masked=sanitize_text(evidence),
                    )
                )
        return findings


def _default_regex_rules() -> list[RegexRule]:
    return [
        RegexRule(
            "regex_phone_number",
            "privacy_leak",
            RiskLevel.LOW,
            re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
            "检测到手机号，允许继续但需要脱敏记录。",
        ),
        RegexRule(
            "regex_id_card",
            "privacy_leak",
            RiskLevel.HIGH,
            re.compile(r"(?<!\d)\d{6}(?:19|20)\d{2}\d{7}[\dXx](?!\d)"),
            "检测到身份证号，属于高风险隐私内容。",
        ),
        RegexRule(
            "regex_bank_card",
            "privacy_leak",
            RiskLevel.HIGH,
            re.compile(r"(?<!\d)\d{16,19}(?!\d)"),
            "检测到银行卡号，属于高风险隐私内容。",
        ),
        RegexRule(
            "regex_email",
            "privacy_leak",
            RiskLevel.LOW,
            re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
            "检测到邮箱地址，允许继续但需要脱敏记录。",
        ),
        RegexRule(
            "regex_api_key",
            "privacy_leak",
            RiskLevel.CRITICAL,
            re.compile(r"(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|ak-[A-Za-z0-9_-]{12,}|api[_-]?key[:=][A-Za-z0-9_-]{8,})\b"),
            "检测到疑似密钥或令牌。",
        ),
        RegexRule(
            "regex_prompt_injection",
            "prompt_injection",
            RiskLevel.HIGH,
            re.compile(r"(?i)(忽略|无视|绕过).{0,12}(之前|以上|系统|开发者|指令|规则)|system\s*prompt|developer\s*message"),
            "检测到提示词注入表达。",
        ),
    ]
