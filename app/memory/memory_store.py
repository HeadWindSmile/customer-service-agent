from collections import defaultdict, deque

from app.config import settings
from app.memory.base import BaseConversationMemory


class InMemoryConversationMemory(BaseConversationMemory):
    """第一阶段用进程内存保留最近 8 轮，满足单机演示并预留 Redis 替换点。"""

    def __init__(self, max_turns: int | None = None) -> None:
        self.max_turns = max_turns or settings.memory_max_turns
        self._store: dict[str, deque[dict[str, str]]] = defaultdict(lambda: deque(maxlen=self.max_turns))

    def add_turn(self, session_id: str, user_message: str, assistant_answer: str) -> None:
        self._store[session_id].append({"user": user_message, "assistant": assistant_answer})

    def get_recent(self, session_id: str) -> list[dict[str, str]]:
        return list(self._store[session_id])

