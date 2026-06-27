import hashlib
import math
from abc import ABC, abstractmethod


class BaseEmbedding(ABC):
    """Embedding 抽象层让本地 mock 和后续真实 BGE/qwen 向量模型可以替换。"""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError


class MockEmbedding(BaseEmbedding):
    """确定性的轻量 embedding，保证没有 API Key 时也能跑完整 RAG 链路。"""

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for char in text:
            if not char.strip():
                continue
            index = int(hashlib.md5(char.encode("utf-8")).hexdigest(), 16) % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / norm, 6) for value in vector]


class DashScopeEmbedding(BaseEmbedding):
    """通义千问 embedding 预留接口；第 2 阶段默认不调用外部服务。"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("当前阶段默认使用 MockEmbedding，后续阶段再接 DashScope。")

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError("当前阶段默认使用 MockEmbedding，后续阶段再接 DashScope。")


class OpenAICompatibleEmbedding(BaseEmbedding):
    """OpenAI-compatible embedding 预留接口；保持扩展点但不增加运行时依赖。"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("当前阶段默认使用 MockEmbedding，后续阶段再接 OpenAI-compatible API。")

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError("当前阶段默认使用 MockEmbedding，后续阶段再接 OpenAI-compatible API。")


def create_embedding(provider: str) -> BaseEmbedding:
    if provider == "mock":
        return MockEmbedding()
    if provider == "dashscope":
        return DashScopeEmbedding()
    if provider == "openai_compatible":
        return OpenAICompatibleEmbedding()
    return MockEmbedding()
