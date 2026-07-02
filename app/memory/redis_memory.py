import json
from time import time
from typing import Any

from app.config import settings
from app.memory.base import MemoryMessage, MemoryRole, MemoryStore


class RedisMemory(MemoryStore):
    """Redis 版会话记忆。

    Redis key 以 user_id + session_id 共同组成，解决多用户会话串线问题；recent、summary、
    key_facts 拆成独立 key，是为了让最近消息走 list，摘要和事实走简单 JSON 字符串。
    """

    backend_name = "redis"

    def __init__(
        self,
        redis_url: str | None = None,
        ttl_seconds: int | None = None,
        max_turns: int | None = None,
        client: Any | None = None,
    ) -> None:
        self.redis_url = redis_url or settings.redis_url
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else settings.memory_ttl_seconds
        self.max_messages = (max_turns or settings.memory_recent_turns) * 2
        self._client = client

    async def ping(self) -> None:
        client = await self._get_client()
        await client.ping()

    async def append_message(
        self,
        user_id: str,
        session_id: str,
        role: MemoryRole,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        client = await self._get_client()
        key = self._recent_key(user_id, session_id)
        message = MemoryMessage(role=role, content=content, created_at=time(), metadata=metadata or {})
        await client.rpush(key, json.dumps(message.to_dict(), ensure_ascii=False))
        await self._expire_session_keys(client, user_id, session_id)

    async def get_recent_messages(
        self,
        user_id: str,
        session_id: str,
        limit: int | None = None,
    ) -> list[MemoryMessage]:
        client = await self._get_client()
        limit = limit or self.max_messages
        rows = await client.lrange(self._recent_key(user_id, session_id), -limit, -1)
        return [MemoryMessage.from_dict(_json_load(row)) for row in rows]

    async def get_summary(self, user_id: str, session_id: str) -> str:
        client = await self._get_client()
        value = await client.get(self._summary_key(user_id, session_id))
        return _decode(value) if value else ""

    async def update_summary(self, user_id: str, session_id: str, summary: str) -> None:
        client = await self._get_client()
        await client.set(self._summary_key(user_id, session_id), summary)
        await self._expire_session_keys(client, user_id, session_id)

    async def get_key_facts(self, user_id: str, session_id: str) -> dict[str, Any]:
        client = await self._get_client()
        value = await client.get(self._facts_key(user_id, session_id))
        return _json_load(value) if value else {}

    async def update_key_facts(self, user_id: str, session_id: str, key_facts: dict[str, Any]) -> None:
        client = await self._get_client()
        await client.set(self._facts_key(user_id, session_id), json.dumps(key_facts, ensure_ascii=False))
        await self._expire_session_keys(client, user_id, session_id)

    async def trim_recent_messages(self, user_id: str, session_id: str, max_messages: int) -> None:
        client = await self._get_client()
        await client.ltrim(self._recent_key(user_id, session_id), -max_messages, -1)
        await self._expire_session_keys(client, user_id, session_id)

    async def clear_session(self, user_id: str, session_id: str) -> None:
        client = await self._get_client()
        await client.delete(
            self._recent_key(user_id, session_id),
            self._summary_key(user_id, session_id),
            self._facts_key(user_id, session_id),
        )

    async def _get_client(self) -> Any:
        if self._client is None:
            try:
                import redis.asyncio as redis
            except Exception as exc:
                raise RuntimeError("redis.asyncio 不可用，无法创建 RedisMemory。") from exc
            self._client = redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    async def _expire_session_keys(self, client: Any, user_id: str, session_id: str) -> None:
        if self.ttl_seconds <= 0:
            return
        for key in [
            self._recent_key(user_id, session_id),
            self._summary_key(user_id, session_id),
            self._facts_key(user_id, session_id),
        ]:
            await client.expire(key, self.ttl_seconds)

    def _base_key(self, user_id: str, session_id: str) -> str:
        return f"customer_agent:{user_id}:{session_id}"

    def _recent_key(self, user_id: str, session_id: str) -> str:
        return f"{self._base_key(user_id, session_id)}:recent_messages"

    def _summary_key(self, user_id: str, session_id: str) -> str:
        return f"{self._base_key(user_id, session_id)}:summary"

    def _facts_key(self, user_id: str, session_id: str) -> str:
        return f"{self._base_key(user_id, session_id)}:key_facts"


def _decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _json_load(value: Any) -> dict[str, Any]:
    return json.loads(_decode(value))

