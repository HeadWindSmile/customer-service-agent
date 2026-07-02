from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


MemoryRole = Literal["user", "assistant"]


@dataclass
class MemoryMessage:
    """统一的会话消息结构。

    memory 层使用结构化对象而不是裸 dict，是为了让 Redis JSON 序列化、内存 fallback
    和 prompt 组装共享同一种语义，避免后续多轮上下文扩展时到处猜字段含义。
    """

    role: MemoryRole
    content: str
    created_at: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryMessage":
        role = "assistant" if data.get("role") == "assistant" else "user"
        return cls(
            role=role,
            content=str(data.get("content", "")),
            created_at=float(data.get("created_at", 0)),
            metadata=dict(data.get("metadata") or {}),
        )


class MemoryStore(ABC):
    """会话记忆统一接口。

    Redis 和本地内存都实现这组异步方法，CustomerAgent 只依赖抽象。
    这样本地最小版本可以无 Redis 启动，部署到多实例时又可以切到 Redis 共享上下文。
    """

    backend_name = "unknown"

    @abstractmethod
    async def append_message(
        self,
        user_id: str,
        session_id: str,
        role: MemoryRole,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_recent_messages(
        self,
        user_id: str,
        session_id: str,
        limit: int | None = None,
    ) -> list[MemoryMessage]:
        raise NotImplementedError

    @abstractmethod
    async def get_summary(self, user_id: str, session_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def update_summary(self, user_id: str, session_id: str, summary: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_key_facts(self, user_id: str, session_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def update_key_facts(self, user_id: str, session_id: str, key_facts: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def trim_recent_messages(self, user_id: str, session_id: str, max_messages: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def clear_session(self, user_id: str, session_id: str) -> None:
        raise NotImplementedError

