from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.memory.base import MemoryMessage, MemoryStore
from app.memory.key_facts import KeyFactsExtractor
from app.memory.privacy import sanitize_text
from app.memory.summarizer import ConversationSummarizer
from app.schemas.chat import ToolCall


@dataclass
class MemoryContext:
    """CustomerAgent 使用的会话上下文视图。"""

    recent_messages: list[MemoryMessage] = field(default_factory=list)
    recent_turns: list[dict[str, str]] = field(default_factory=list)
    summary: str = ""
    key_facts: dict[str, Any] = field(default_factory=dict)
    backend_name: str = "memory"


class ConversationMemoryManager:
    """会话记忆应用服务。

    Store 只负责存取；Manager 负责把“最近 8 轮 + summary + key_facts”组织成 Agent
    可消费的上下文，避免 CustomerAgent 直接依赖 Redis 数据结构。
    """

    def __init__(
        self,
        store: MemoryStore,
        summarizer: ConversationSummarizer | None = None,
        key_facts_extractor: KeyFactsExtractor | None = None,
        recent_turns: int | None = None,
    ) -> None:
        self.store = store
        self.recent_turns = recent_turns or settings.memory_recent_turns
        self.max_messages = self.recent_turns * 2
        self.summarizer = summarizer or ConversationSummarizer()
        self.key_facts_extractor = key_facts_extractor or KeyFactsExtractor()

    async def load_context(self, user_id: str, session_id: str) -> MemoryContext:
        messages = await self.store.get_recent_messages(user_id, session_id, self.max_messages)
        summary = await self.store.get_summary(user_id, session_id)
        key_facts = await self.store.get_key_facts(user_id, session_id)
        return MemoryContext(
            recent_messages=messages,
            recent_turns=messages_to_turns(messages),
            summary=summary,
            key_facts=key_facts,
            backend_name=self.store.backend_name,
        )

    async def save_turn(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        assistant_answer: str,
        slots: dict[str, Any],
        tool_calls: list[ToolCall],
    ) -> None:
        await self.store.append_message(user_id, session_id, "user", sanitize_text(user_message))
        await self.store.append_message(user_id, session_id, "assistant", sanitize_text(assistant_answer))
        await self._compact_if_needed(user_id, session_id)
        await self._update_key_facts(user_id, session_id, user_message, assistant_answer, slots, tool_calls)

    async def clear_session(self, user_id: str, session_id: str) -> None:
        await self.store.clear_session(user_id, session_id)

    async def _compact_if_needed(self, user_id: str, session_id: str) -> None:
        messages = await self.store.get_recent_messages(user_id, session_id, self.max_messages + 4)
        if len(messages) <= self.max_messages:
            return
        overflow_messages = messages[: -self.max_messages]
        existing_summary = await self.store.get_summary(user_id, session_id)
        new_summary = self.summarizer.summarize(existing_summary, overflow_messages)
        await self.store.update_summary(user_id, session_id, new_summary)
        await self.store.trim_recent_messages(user_id, session_id, self.max_messages)

    async def _update_key_facts(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        assistant_answer: str,
        slots: dict[str, Any],
        tool_calls: list[ToolCall],
    ) -> None:
        existing = await self.store.get_key_facts(user_id, session_id)
        key_facts = self.key_facts_extractor.merge(existing, user_message, assistant_answer, slots, tool_calls)
        await self.store.update_key_facts(user_id, session_id, key_facts)


def messages_to_turns(messages: list[MemoryMessage]) -> list[dict[str, str]]:
    turns: list[dict[str, str]] = []
    current_user = ""
    for message in messages:
        if message.role == "user":
            current_user = message.content
            continue
        if message.role == "assistant":
            turns.append({"user": current_user, "assistant": message.content})
            current_user = ""
    if current_user:
        turns.append({"user": current_user, "assistant": ""})
    return turns

