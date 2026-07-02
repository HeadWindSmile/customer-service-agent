import re
from dataclasses import dataclass
from typing import Any


_TICKET_RE = re.compile(r"TCK-[A-Za-z0-9]{6,}", re.IGNORECASE)
_PACKAGE_NAMES = ["5G畅享套餐", "家庭融合套餐", "校园套餐", "基础套餐"]


@dataclass
class RewriteResult:
    original_query: str
    rewritten_query: str
    changed: bool
    reason: str = ""


class QueryRewriter:
    """基础指代消解。

    这里只做高置信规则改写，避免把用户问题过度“脑补”。真实生产环境可在此基础上
    接入 LLM rewrite 或 reranker，但第六阶段先保持可控、可测试。
    """

    def rewrite(
        self,
        query: str,
        recent_turns: list[dict[str, str]] | None = None,
        key_facts: dict[str, Any] | None = None,
    ) -> RewriteResult:
        original = query.strip()
        key_facts = key_facts or {}
        recent_text = _flatten_turns(recent_turns or [])

        rewritten = original
        reasons: list[str] = []

        package_name = _resolve_package_name(key_facts, recent_text)
        if package_name and _has_any(rewritten, ["这个套餐", "该套餐", "这个资费", "它"]):
            rewritten = rewritten.replace("这个套餐", package_name)
            rewritten = rewritten.replace("该套餐", package_name)
            rewritten = rewritten.replace("这个资费", package_name)
            if "它" in rewritten and _has_any(original, ["多少钱", "怎么收费", "生效", "能退", "能办"]):
                rewritten = rewritten.replace("它", package_name)
            reasons.append("使用最近套餐事实消解指代")

        ticket_id = _resolve_ticket_id(key_facts, recent_text)
        if ticket_id and _has_any(rewritten, ["刚才那个工单", "那个工单", "这个工单", "它"]):
            rewritten = rewritten.replace("刚才那个工单", f"工单 {ticket_id}")
            rewritten = rewritten.replace("那个工单", f"工单 {ticket_id}")
            rewritten = rewritten.replace("这个工单", f"工单 {ticket_id}")
            if "它" in rewritten and _has_any(original, ["进度", "状态", "处理到哪", "怎么样"]):
                rewritten = rewritten.replace("它", f"工单 {ticket_id}")
            reasons.append("使用最近工单事实消解指代")

        bill_month = key_facts.get("last_bill_month")
        if bill_month and _has_any(rewritten, ["这笔费用", "这笔账单", "这个账单", "刚才账单"]):
            rewritten = rewritten.replace("这笔费用", f"{bill_month}账单费用")
            rewritten = rewritten.replace("这笔账单", f"{bill_month}账单")
            rewritten = rewritten.replace("这个账单", f"{bill_month}账单")
            rewritten = rewritten.replace("刚才账单", f"{bill_month}账单")
            reasons.append("使用最近账单月份消解指代")

        changed = rewritten != original
        return RewriteResult(
            original_query=original,
            rewritten_query=rewritten,
            changed=changed,
            reason="；".join(reasons),
        )


def _flatten_turns(turns: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for turn in turns:
        parts.append(str(turn.get("user", "")))
        parts.append(str(turn.get("assistant", "")))
    return "\n".join(parts)


def _resolve_package_name(key_facts: dict[str, Any], recent_text: str) -> str:
    for key in ["target_package", "current_package", "last_product_name"]:
        value = str(key_facts.get(key) or "").strip()
        if value:
            return value
    for package_name in _PACKAGE_NAMES:
        if package_name in recent_text:
            return package_name
    return ""


def _resolve_ticket_id(key_facts: dict[str, Any], recent_text: str) -> str:
    value = str(key_facts.get("last_ticket_id") or "").strip().upper()
    if value:
        return value
    match = _TICKET_RE.search(recent_text)
    return match.group(0).upper() if match else ""


def _has_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)

