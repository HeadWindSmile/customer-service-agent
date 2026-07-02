import json
import os
from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.safety.regex_detector import RegexDetector
from app.safety.risk_level import RiskLevel, SafetyFinding, SafetyResult
from app.safety.sanitizer import sanitize_text
from app.safety.semantic_detector import BaseSemanticDetector, MockSemanticDetector


@dataclass(frozen=True)
class KeywordRule:
    rule_id: str
    risk_type: str
    risk_level: RiskLevel
    keywords: tuple[str, ...]
    message: str
    scopes: tuple[str, ...] = field(default_factory=lambda: ("input", "output", "tool"))


class RuleEngine:
    """内容安全规则引擎。

    规则引擎把关键词、正则和 mock 语义检测统一成 SafetyResult。这样 CustomerAgent
    只关心风险结果和动作，不需要知道每条规则如何命中。
    """

    def __init__(
        self,
        *,
        rules_path: str | None = None,
        regex_detector: RegexDetector | None = None,
        semantic_detector: BaseSemanticDetector | None = None,
    ) -> None:
        self.rules_path = rules_path or settings.safety_rules_path
        self.keyword_rules = self._load_keyword_rules()
        self.regex_detector = regex_detector or RegexDetector()
        self.semantic_detector = semantic_detector or MockSemanticDetector()

    def scan(self, text: str, *, scope: str) -> SafetyResult:
        if not settings.safety_enabled:
            return SafetyResult(scope=scope)
        normalized_text = str(text or "")
        findings: list[SafetyFinding] = []
        findings.extend(self._scan_keywords(normalized_text, scope=scope))
        findings.extend(self.regex_detector.detect(normalized_text, scope=scope))
        findings.extend(self.semantic_detector.detect(normalized_text, scope=scope))
        return SafetyResult(scope=scope, findings=_dedupe_findings(findings))

    def _scan_keywords(self, text: str, *, scope: str) -> list[SafetyFinding]:
        findings: list[SafetyFinding] = []
        for rule in self.keyword_rules:
            if scope not in rule.scopes and "all" not in rule.scopes:
                continue
            for keyword in rule.keywords:
                if keyword and keyword in text:
                    findings.append(
                        SafetyFinding(
                            risk_type=rule.risk_type,
                            risk_level=rule.risk_level,
                            source="keyword",
                            rule_id=rule.rule_id,
                            message=rule.message,
                            evidence_masked=sanitize_text(keyword),
                        )
                    )
                    break
        return findings

    def _load_keyword_rules(self) -> list[KeywordRule]:
        loaded = _load_config_rules(self.rules_path)
        rules = [_keyword_rule_from_dict(item) for item in loaded if item.get("keywords")]
        rules.extend(_env_compat_rules())
        if rules:
            return rules
        return _default_keyword_rules()


def _load_config_rules(path: str) -> list[dict[str, Any]]:
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as file:
        raw = file.read().strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore

            payload = yaml.safe_load(raw)
        except Exception:
            return []
    if isinstance(payload, dict):
        rules = payload.get("rules", [])
        return [item for item in rules if isinstance(item, dict)]
    return []


def _keyword_rule_from_dict(item: dict[str, Any]) -> KeywordRule:
    return KeywordRule(
        rule_id=str(item.get("id") or item.get("rule_id") or "keyword_rule"),
        risk_type=str(item.get("risk_type") or "sensitive_keyword"),
        risk_level=RiskLevel(str(item.get("risk_level") or "HIGH").upper()),
        keywords=tuple(str(keyword) for keyword in item.get("keywords", []) if str(keyword).strip()),
        message=str(item.get("message") or item.get("description") or "命中内容安全关键词。"),
        scopes=tuple(str(scope) for scope in item.get("scopes", ["input", "output", "tool"])),
    )


def _env_compat_rules() -> list[KeywordRule]:
    rules: list[KeywordRule] = []
    if settings.safety_blocked_words:
        rules.append(
            KeywordRule(
                rule_id="env_safety_blocked_words",
                risk_type="sensitive_keyword",
                risk_level=RiskLevel.HIGH,
                keywords=tuple(settings.safety_blocked_words),
                message="命中输入敏感词，已拦截。",
                scopes=("input", "tool"),
            )
        )
    if settings.output_forbidden_phrases:
        rules.append(
            KeywordRule(
                rule_id="env_output_forbidden_phrases",
                risk_type="price_commitment",
                risk_level=RiskLevel.HIGH,
                keywords=tuple(settings.output_forbidden_phrases),
                message="命中输出高危承诺短语。",
                scopes=("output",),
            )
        )
    return rules


def _default_keyword_rules() -> list[KeywordRule]:
    return [
        KeywordRule(
            "default_prompt_injection",
            "prompt_injection",
            RiskLevel.HIGH,
            ("忽略之前指令", "绕过权限", "系统提示词"),
            "命中提示词注入关键词。",
            ("input", "tool"),
        )
    ]


def _dedupe_findings(findings: list[SafetyFinding]) -> list[SafetyFinding]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[SafetyFinding] = []
    for finding in findings:
        key = (finding.risk_type, finding.rule_id, finding.evidence_masked)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique
