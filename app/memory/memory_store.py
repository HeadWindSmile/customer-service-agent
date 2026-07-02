from collections import defaultdict
from time import time
from typing import Any

from app.config import settings
from app.memory.base import MemoryMessage, MemoryRole, MemoryStore


class InMemoryMemoryStore(MemoryStore):
    """进程内 memory fallback。

    它不解决多实例共享问题，但保留完整 MemoryStore 接口，保证 Redis 不可用时
    本地 demo 和 pytest 仍然能跑通。同一套接口也让后续迁移 Redis Cluster 更平滑。
    """

    backend_name = "memory"

    def __init__(self, max_turns: int | None = None) -> None:
        self.max_messages = (max_turns or settings.memory_recent_turns) * 2
        self._messages: dict[str, list[MemoryMessage]] = defaultdict(list)
        self._summaries: dict[str, str] = defaultdict(str)
        self._key_facts: dict[str, dict[str, Any]] = defaultdict(dict)

    async def append_message(
        self,
        user_id: str,
        session_id: str,
        role: MemoryRole,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._messages[_session_key(user_id, session_id)].append(
            MemoryMessage(role=role, content=content, created_at=time(), metadata=metadata or {})
        )

    async def get_recent_messages(
        self,
        user_id: str,
        session_id: str,
        limit: int | None = None,
    ) -> list[MemoryMessage]:
        messages = self._messages[_session_key(user_id, session_id)]
        if limit is None:
            limit = self.max_messages
        return list(messages[-limit:])

    async def get_summary(self, user_id: str, session_id: str) -> str:
        return self._summaries[_session_key(user_id, session_id)]

    async def update_summary(self, user_id: str, session_id: str, summary: str) -> None:
        self._summaries[_session_key(user_id, session_id)] = summary

    async def get_key_facts(self, user_id: str, session_id: str) -> dict[str, Any]:
        return dict(self._key_facts[_session_key(user_id, session_id)])

    async def update_key_facts(self, user_id: str, session_id: str, key_facts: dict[str, Any]) -> None:
        self._key_facts[_session_key(user_id, session_id)] = dict(key_facts)

    async def trim_recent_messages(self, user_id: str, session_id: str, max_messages: int) -> None:
        key = _session_key(user_id, session_id)
        self._messages[key] = self._messages[key][-max_messages:]

    async def clear_session(self, user_id: str, session_id: str) -> None:
        key = _session_key(user_id, session_id)
        self._messages.pop(key, None)
        self._summaries.pop(key, None)
        self._key_facts.pop(key, None)


# 保留旧类名，避免已有代码或测试在迁移期需要大规模调整。
InMemoryConversationMemory = InMemoryMemoryStore


def _session_key(user_id: str, session_id: str) -> str:
    return f"{user_id}:{session_id}"

