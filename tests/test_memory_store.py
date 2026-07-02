import asyncio

from app.memory.manager import ConversationMemoryManager
from app.memory.memory_store import InMemoryMemoryStore


def test_in_memory_store_isolates_by_user_id_and_session_id():
    async def scenario():
        store = InMemoryMemoryStore(max_turns=8)
        await store.append_message("u1001", "same-session", "user", "用户1的问题")
        await store.append_message("u1002", "same-session", "user", "用户2的问题")

        user1_messages = await store.get_recent_messages("u1001", "same-session")
        user2_messages = await store.get_recent_messages("u1002", "same-session")

        assert [message.content for message in user1_messages] == ["用户1的问题"]
        assert [message.content for message in user2_messages] == ["用户2的问题"]

    asyncio.run(scenario())


def test_memory_manager_keeps_recent_turns_and_writes_summary():
    async def scenario():
        store = InMemoryMemoryStore(max_turns=2)
        manager = ConversationMemoryManager(store, recent_turns=2)

        for index in range(3):
            await manager.save_turn(
                "u1001",
                "summary-session",
                f"第{index}轮用户问题",
                f"第{index}轮客服回答",
                slots={},
                tool_calls=[],
            )

        context = await manager.load_context("u1001", "summary-session")

        assert len(context.recent_turns) == 2
        assert context.recent_turns[0]["user"] == "第1轮用户问题"
        assert "第0轮用户问题" in context.summary

    asyncio.run(scenario())


def test_memory_manager_key_facts_are_sanitized():
    async def scenario():
        store = InMemoryMemoryStore(max_turns=8)
        manager = ConversationMemoryManager(store)

        await manager.save_turn(
            "u1001",
            "facts-session",
            "我的手机号是13812345678，帮我查本月账单",
            "本月账单金额为 156.8 元。",
            slots={"month": "本月", "phone_number": "138****5678"},
            tool_calls=[],
        )
        facts = (await manager.load_context("u1001", "facts-session")).key_facts

        assert facts["last_bill_month"] == "本月"
        assert "phone_number" not in facts
        assert "13812345678" not in str(facts)

    asyncio.run(scenario())

