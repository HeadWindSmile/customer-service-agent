import re
from typing import Any


_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
_ID_CARD_RE = re.compile(r"(?<!\d)(\d{6}(?:19|20)\d{2}\d{7}[\dXx])(?!\d)")
_BANK_CARD_RE = re.compile(r"(?<!\d)(\d{16,19})(?!\d)")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_SECRET_RE = re.compile(
    r"(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|ak-[A-Za-z0-9_-]{12,}|api[_-]?key[:=][A-Za-z0-9_-]{8,})\b"
)

_SENSITIVE_KEYWORDS = {
    "user_id",
    "target_user_id",
    "current_user_id",
    "actor_user_id",
    "phone",
    "phone_number",
    "mobile",
    "id_card",
    "identity",
    "bank_card",
    "password",
    "token",
    "secret",
    "api_key",
}


def mask_identifier(value: Any) -> str:
    text = str(value)
    if len(text) <= 2:
        return "*" * len(text)
    if len(text) <= 6:
        return f"{text[0]}***{text[-1]}"
    return f"{text[:2]}***{text[-2:]}"


def sanitize_text(text: str) -> str:
    """脱敏安全日志中的证据文本。

    safety 模块的脱敏职责覆盖 trace、review queue 和 tool_calls 展示；它和
    memory/privacy.py 的目的不同，后者主要保护会话存储不记住隐私。
    """

    sanitized = _PHONE_RE.sub(lambda match: f"{match.group(1)[:3]}****{match.group(1)[-4:]}", text)
    sanitized = _ID_CARD_RE.sub("[身份证号已脱敏]", sanitized)
    sanitized = _BANK_CARD_RE.sub("[银行卡号已脱敏]", sanitized)
    sanitized = _EMAIL_RE.sub("[邮箱已脱敏]", sanitized)
    sanitized = _SECRET_RE.sub("[密钥已脱敏]", sanitized)
    return sanitized


def sanitize_value(value: Any, *, key: str | None = None) -> Any:
    lowered_key = (key or "").lower()
    if isinstance(value, str):
        if lowered_key in _SENSITIVE_KEYWORDS or lowered_key.endswith("user_id"):
            return mask_identifier(value)
        return sanitize_text(value)
    if isinstance(value, dict):
        return {item_key: sanitize_value(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    return value
