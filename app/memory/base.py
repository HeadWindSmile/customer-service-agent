from abc import ABC, abstractmethod


class BaseConversationMemory(ABC):
    """记忆抽象层让本地内存和后续 Redis Cluster 可以平滑替换。"""

    @abstractmethod
    def add_turn(self, session_id: str, user_message: str, assistant_answer: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_recent(self, session_id: str) -> list[dict[str, str]]:
        raise NotImplementedError

