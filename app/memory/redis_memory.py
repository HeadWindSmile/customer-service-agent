from app.memory.base import BaseConversationMemory


class RedisMemory(BaseConversationMemory):
    """Redis 记忆占位类；第 1 阶段不连接 Redis，避免本地启动依赖外部服务。"""

    def add_turn(self, session_id: str, user_message: str, assistant_answer: str) -> None:
        raise NotImplementedError("第 1 阶段使用 InMemoryConversationMemory。")

    def get_recent(self, session_id: str) -> list[dict[str, str]]:
        raise NotImplementedError("第 1 阶段使用 InMemoryConversationMemory。")

