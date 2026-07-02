from collections.abc import Sequence

from langchain_core.runnables import Runnable

from app.llm.factory import create_llm_client
from app.llm.mock_llm import MockLLM
from app.memory.base import MemoryMessage
from app.memory.privacy import sanitize_text
from app.observability.logger import log_event


class ConversationSummarizer:
    """Summary Buffer 压缩器。

    最近 8 轮保留原文，更早历史压缩成摘要。这样 prompt 不会无限增长，也能在用户
    多轮追问时保留“之前讨论过什么”的低成本上下文。
    """

    def __init__(self, llm: Runnable | None = None, max_chars: int = 700) -> None:
        self.llm = llm or create_llm_client().as_runnable()
        self.fallback_llm = MockLLM().as_runnable()
        self.max_chars = max_chars

    def summarize(self, existing_summary: str, overflow_messages: Sequence[MemoryMessage]) -> str:
        if not overflow_messages:
            return existing_summary

        prompt = (
            "CONVERSATION_SUMMARY\n"
            "请把客服多轮对话压缩成简洁摘要，只保留业务上下文，不保留手机号、身份证、银行卡等隐私字段。\n\n"
            f"已有摘要：\n{existing_summary or '无'}\n\n"
            f"新增历史：\n{_format_messages(overflow_messages)}\n\n"
            "输出新的摘要："
        )
        try:
            summary = self.llm.invoke(prompt).strip()
        except Exception as exc:
            log_event("memory.summary_llm_failed", {"error": str(exc)}, level="error")
            summary = self.fallback_llm.invoke(prompt).strip()
        return _clip(sanitize_text(summary), self.max_chars)


def _format_messages(messages: Sequence[MemoryMessage]) -> str:
    lines: list[str] = []
    for message in messages:
        role = "用户" if message.role == "user" else "客服"
        lines.append(f"{role}：{sanitize_text(message.content)}")
    return "\n".join(lines)


def _clip(text: str, max_chars: int) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}..."

