from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(str, Enum):
    """内容安全风险等级。

    用枚举而不是散落字符串，是为了让输入、输出、工具参数检测都共享同一套
    风险语义，后续接入真实安全审核服务时也能保持响应结构稳定。
    """

    SAFE = "SAFE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SafetyAction(str, Enum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"


_RISK_ORDER = {
    RiskLevel.SAFE: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}


def risk_at_least(level: RiskLevel, threshold: RiskLevel) -> bool:
    return _RISK_ORDER[level] >= _RISK_ORDER[threshold]


def max_risk(levels: list[RiskLevel]) -> RiskLevel:
    if not levels:
        return RiskLevel.SAFE
    return max(levels, key=lambda item: _RISK_ORDER[item])


def action_for_level(level: RiskLevel) -> SafetyAction:
    if risk_at_least(level, RiskLevel.HIGH):
        return SafetyAction.BLOCK
    if level == RiskLevel.MEDIUM:
        return SafetyAction.REVIEW
    return SafetyAction.ALLOW


@dataclass(frozen=True)
class SafetyFinding:
    risk_type: str
    risk_level: RiskLevel
    source: str
    rule_id: str
    message: str
    evidence_masked: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "risk_type": self.risk_type,
            "risk_level": self.risk_level.value,
            "source": self.source,
            "rule_id": self.rule_id,
            "message": self.message,
            "evidence_masked": self.evidence_masked,
        }


@dataclass
class SafetyResult:
    scope: str
    findings: list[SafetyFinding] = field(default_factory=list)

    @property
    def risk_level(self) -> RiskLevel:
        return max_risk([finding.risk_level for finding in self.findings])

    @property
    def action(self) -> SafetyAction:
        return action_for_level(self.risk_level)

    @property
    def allowed(self) -> bool:
        return self.action == SafetyAction.ALLOW

    @property
    def should_review(self) -> bool:
        return risk_at_least(self.risk_level, RiskLevel.MEDIUM)

    def to_dict(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "risk_level": self.risk_level.value,
            "action": self.action.value,
            "allowed": self.allowed,
            "should_review": self.should_review,
            "findings": [finding.to_dict() for finding in self.findings],
        }
