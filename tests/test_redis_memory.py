import asyncio
from collections import defaultdict

from app.memory.factory import FallbackMemoryStore
from app.memory.memory_store import InMemoryMemoryStore
from app.memory.redis_memory import RedisMemory


class FakeRedis:
    def __init__(self) -> None:
        self.lists = defaultdict(list)
        self.values = {}
        self.expired_keys = []

    async def ping(self):
        return True

    async def rpush(self, key, value):
        self.lists[key].append(value)

    async def lrange(self, key, start, end):
        values = self.lists[key]
        if start < 0:
            start = max(len(values) + start, 0)
        if end < 0:
            end = len(values) + end
        return values[start : end + 1]

    async def ltrim(self, key, start, end):
        values = self.lists[key]
        if start < 0:
            start = max(len(values) + start, 0)
        if end < 0:
            end = len(values) + end
        self.lists[key] = values[start : end + 1]

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value):
        self.values[key] = value

    async def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.lists.pop(key, None)

    async def expire(self, key, ttl):
        self.expired_keys.append((key, ttl))


class FailingStore(InMemoryMemoryStore):
    backend_name = "redis"

    async def get_recent_messages(self, user_id, session_id, limit=None):
        raise RuntimeError("redis down")


def test_redis_memory_reads_and_trims_recent_messages():
    async def scenario():
        fake = FakeRedis()
        memory = RedisMemory(ttl_seconds=60, max_turns=1, client=fake)
        await memory.append_message("u1001", "s1", "user", "第一问")
        await memory.append_message("u1001", "s1", "assistant", "第一答")
        await memory.append_message("u1001", "s1", "user", "第二问")

        await memory.trim_recent_messages("u1001", "s1", 2)
        messages = await memory.get_recent_messages("u1001", "s1", 2)

        assert [message.content for message in messages] == ["第一答", "第二问"]
        assert any(key.endswith(":recent_messages") and ttl == 60 for key, ttl in fake.expired_keys)

    asyncio.run(scenario())


def test_redis_memory_summary_and_key_facts_round_trip():
    async def scenario():
        memory = RedisMemory(ttl_seconds=60, client=FakeRedis())
        await memory.update_summary("u1001", "s1", "用户咨询过5G畅享套餐")
        await memory.update_key_facts("u1001", "s1", {"target_package": "5G畅享套餐"})

        assert await memory.get_summary("u1001", "s1") == "用户咨询过5G畅享套餐"
        assert await memory.get_key_facts("u1001", "s1") == {"target_package": "5G畅享套餐"}

        await memory.clear_session("u1001", "s1")
        assert await memory.get_summary("u1001", "s1") == ""
        assert await memory.get_key_facts("u1001", "s1") == {}

    asyncio.run(scenario())


def test_fallback_memory_store_switches_to_memory_when_primary_fails():
    async def scenario():
        fallback = InMemoryMemoryStore()
        store = FallbackMemoryStore(FailingStore(), fallback)

        messages = await store.get_recent_messages("u1001", "s1")

        assert messages == []
        assert store.backend_name == "memory"

    asyncio.run(scenario())

