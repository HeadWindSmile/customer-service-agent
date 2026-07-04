import hashlib
import math
from abc import ABC, abstractmethod
from collections.abc import Iterable

from app.config import settings


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


class OpenAICompatibleEmbedding(BaseEmbedding):
    """OpenAI-compatible embedding 适配器。

    阿里云百炼和很多企业模型网关都兼容 OpenAI embeddings 接口。RAG 层只依赖
    BaseEmbedding，可以在 mock、DashScope 和企业私有网关之间切换。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        dimensions: int | None = None,
        timeout_seconds: float = 10,
    ) -> None:
        if not api_key:
            raise RuntimeError("Embedding API Key 未配置。")
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.dimensions = dimensions
        self.timeout_seconds = timeout_seconds
        self.fallback = MockEmbedding()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            return [item for batch in _batched(texts, 10) for item in self._embed_batch(batch)]
        except Exception:
            # 外部 embedding 不可用时降级到 mock，保证本地服务仍能启动和演示。
            return self.fallback.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_documents([text])
        return vectors[0] if vectors else self.fallback.embed_query(text)

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout_seconds)
        kwargs: dict[str, object] = {"model": self.model_name, "input": texts}
        if self.dimensions:
            kwargs["dimensions"] = self.dimensions
        response = client.embeddings.create(**kwargs)
        return [list(item.embedding) for item in response.data]


class DashScopeEmbedding(OpenAICompatibleEmbedding):
    """阿里云百炼 text-embedding-v4 适配器，默认使用 DashScope 兼容接口。"""

    def __init__(self) -> None:
        super().__init__(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
            model_name=settings.embedding_model_name,
            dimensions=settings.embedding_dimensions,
            timeout_seconds=settings.embedding_timeout_seconds,
        )


class BGEEmbedding(BaseEmbedding):
    """BGE 中文向量模型适配器。

    这里通过 lazy import 接入 sentence-transformers，避免默认本地模式安装大型
    模型依赖。配置 `EMBEDDING_PROVIDER=bge` 且依赖/模型可用时走真实 BGE；
    任何加载或推理失败都会回退到 MockEmbedding，保证 Demo 最小链路仍可启动。
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        normalize_embeddings: bool = True,
    ) -> None:
        self.model_name = model_name or settings.bge_embedding_model_name
        self.device = device if device is not None else settings.bge_embedding_device
        self.normalize_embeddings = normalize_embeddings
        self.fallback = MockEmbedding(dimensions=settings.embedding_dimensions)
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:
            raise RuntimeError("未安装 sentence-transformers，BGE embedding 已降级到 mock。") from exc

        kwargs = {"device": self.device} if self.device else {}
        self.model = SentenceTransformer(self.model_name, **kwargs)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors = self.model.encode(
                texts,
                normalize_embeddings=self.normalize_embeddings,
                show_progress_bar=False,
            )
            return [[float(value) for value in vector] for vector in vectors]
        except Exception:
            return self.fallback.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_documents([text])
        return vectors[0] if vectors else self.fallback.embed_query(text)


def create_embedding(provider: str) -> BaseEmbedding:
    provider = (provider or "mock").lower()
    if provider == "mock":
        return MockEmbedding()
    if provider == "dashscope":
        try:
            return DashScopeEmbedding()
        except Exception:
            return MockEmbedding()
    if provider == "openai_compatible":
        try:
            return OpenAICompatibleEmbedding(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model_name=settings.embedding_model_name,
                dimensions=settings.embedding_dimensions,
                timeout_seconds=settings.embedding_timeout_seconds,
            )
        except Exception:
            return MockEmbedding()
    if provider == "bge":
        try:
            return BGEEmbedding(normalize_embeddings=settings.bge_normalize_embeddings)
        except Exception:
            return MockEmbedding()
    return MockEmbedding()


def _batched(items: list[str], batch_size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]
