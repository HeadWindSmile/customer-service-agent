from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.config import settings
from app.memory.base import MemoryMessage, MemoryRole, MemoryStore
from app.memory.memory_store import InMemoryMemoryStore
from app.memory.redis_memory import RedisMemory
from app.observability.logger import log_event


T = TypeVar("T")


class FallbackMemoryStore(MemoryStore):
    """Redis 运行期异常时自动切到内存。

    企业系统里外部依赖不能拖垮主链路；这里的 fallback 保证 Redis 重启、网络异常或
    依赖缺失时，/api/chat 仍然可以继续使用，只是会降级为单进程会话。
    """

    def __init__(self, primary: MemoryStore, fallback: MemoryStore) -> None:
        self.primary = primary
        self.fallback = fallback
        self.fallback_active = False

    @property
    def backend_name(self) -> str:
        return self.fallback.backend_name if self.fallback_active else self.primary.backend_name

    async def append_message(
        self,
        user_id: str,
        session_id: str,
        role: MemoryRole,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._call(
            lambda store: store.append_message(user_id, session_id, role, content, metadata),
        )

    async def get_recent_messages(
        self,
        user_id: str,
        session_id: str,
        limit: int | None = None,
    ) -> list[MemoryMessage]:
        return await self._call(lambda store: store.get_recent_messages(user_id, session_id, limit))

    async def get_summary(self, user_id: str, session_id: str) -> str:
        return await self._call(lambda store: store.get_summary(user_id, session_id))

    async def update_summary(self, user_id: str, session_id: str, summary: str) -> None:
        await self._call(lambda store: store.update_summary(user_id, session_id, summary))

    async def get_key_facts(self, user_id: str, session_id: str) -> dict[str, Any]:
        return await self._call(lambda store: store.get_key_facts(user_id, session_id))

    async def update_key_facts(self, user_id: str, session_id: str, key_facts: dict[str, Any]) -> None:
        await self._call(lambda store: store.update_key_facts(user_id, session_id, key_facts))

    async def trim_recent_messages(self, user_id: str, session_id: str, max_messages: int) -> None:
        await self._call(lambda store: store.trim_recent_messages(user_id, session_id, max_messages))

    async def clear_session(self, user_id: str, session_id: str) -> None:
        await self._call(lambda store: store.clear_session(user_id, session_id))

    async def _call(self, action: Callable[[MemoryStore], Awaitable[T]]) -> T:
        if self.fallback_active:
            return await action(self.fallback)
        try:
            return await action(self.primary)
        except Exception as exc:
            self.fallback_active = True
            log_event(
                "memory.redis_fallback",
                {"error": str(exc), "fallback_backend": self.fallback.backend_name},
                level="error",
            )
            return await action(self.fallback)


def create_memory_store() -> MemoryStore:
    """根据配置创建 memory backend。

    默认使用本地内存；配置 Redis 时也包一层 fallback，避免 Redis 不可用影响本地演示。
    """

    fallback = InMemoryMemoryStore()
    if settings.memory_backend != "redis":
        return fallback
    try:
        return FallbackMemoryStore(RedisMemory(), fallback)
    except Exception as exc:
        log_event("memory.redis_init_failed", {"error": str(exc)}, level="error")
        return fallback

