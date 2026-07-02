import re
from typing import Any


_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
_ID_CARD_RE = re.compile(r"(?<!\d)(\d{6}(?:19|20)\d{2}\d{7}[\dXx])(?!\d)")
_BANK_CARD_RE = re.compile(r"(?<!\d)(\d{16,19})(?!\d)")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

SAFE_FACT_KEYS = {
    "current_package",
    "target_package",
    "last_bill_month",
    "last_ticket_id",
    "last_issue_type",
    "last_product_name",
}


def sanitize_text(text: str) -> str:
    """脱敏进入 memory 的文本。

    最近对话虽然不是长期事实，但 Redis 仍属于跨进程共享存储，所以在写入前统一处理
    明显隐私字段，避免演示项目形成“把敏感字段原样记住”的坏习惯。
    """

    sanitized = _PHONE_RE.sub(lambda m: f"{m.group(1)[:3]}****{m.group(1)[-4:]}", text)
    sanitized = _ID_CARD_RE.sub("[身份证号已脱敏]", sanitized)
    sanitized = _BANK_CARD_RE.sub("[银行卡号已脱敏]", sanitized)
    sanitized = _EMAIL_RE.sub("[邮箱已脱敏]", sanitized)
    return sanitized


def sanitize_key_facts(key_facts: dict[str, Any]) -> dict[str, Any]:
    """长期 key_facts 只保留业务上下文白名单字段。"""

    sanitized: dict[str, Any] = {}
    for key in SAFE_FACT_KEYS:
        value = key_facts.get(key)
        if value is None or value == "":
            continue
        sanitized[key] = sanitize_text(str(value))
    return sanitized

