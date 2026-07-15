from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import settings
from app.schemas.chat import Source


class BaseReranker(ABC):
    """Reranker 抽象层。

    Retriever 只依赖这个接口，因此本地 Mock、BGE-Reranker 和企业网关的
    OpenAI-compatible rerank 服务可以互换；外部依赖不可用时由工厂降级。
    """

    @abstractmethod
    def rerank(self, query: str, sources: list[Source], top_k: int) -> list[Source]:
        raise NotImplementedError


class MockReranker(BaseReranker):
    """确定性 mock reranker。

    它不会调用外部模型，只把向量库分数和轻量中文词面重合度结合起来，保证本地
    pytest 和演示环境稳定可运行，同时保留真实 reranker 的接口形状。
    """

    def rerank(self, query: str, sources: list[Source], top_k: int) -> list[Source]:
        query_terms = _text_terms(query)
        reranked: list[Source] = []
        for source in sources:
            lexical_score = _lexical_similarity(query_terms, f"{source.title} {source.content}")
            rerank_score = source.score * 0.85 + lexical_score * 0.15
            reranked.append(_copy_with_rerank_score(source, "mock", rerank_score))
        return sorted(reranked, key=lambda item: item.score, reverse=True)[:top_k]


class BGEReranker(BaseReranker):
    """BGE-Reranker 适配器，依赖 FlagEmbedding 时才会启用。"""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.bge_reranker_model_name
        try:
            from FlagEmbedding import FlagReranker  # type: ignore
        except ImportError as exc:
            raise RuntimeError("未安装 FlagEmbedding，BGE reranker 已降级到 mock。") from exc
        self.model = FlagReranker(self.model_name, use_fp16=False)

    def rerank(self, query: str, sources: list[Source], top_k: int) -> list[Source]:
        if not sources:
            return []
        pairs = [[query, source.content] for source in sources]
        raw_scores = self.model.compute_score(pairs)
        scores = raw_scores if isinstance(raw_scores, list) else [raw_scores]
        reranked = [
            _copy_with_rerank_score(source, "bge", float(score))
            for source, score in zip(sources, scores, strict=False)
        ]
        return sorted(reranked, key=lambda item: item.score, reverse=True)[:top_k]


class OpenAICompatibleReranker(BaseReranker):
    """OpenAI-compatible rerank HTTP 适配器。

    不同企业网关的 rerank API 细节略有差异，这里采用常见的 `/rerank` JSON
    契约作为可替换接入点；网关不可用时由调用方 fallback 到 MockReranker。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout_seconds: float = 10,
    ) -> None:
        if not base_url:
            raise RuntimeError("RERANKER_BASE_URL 未配置。")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def rerank(self, query: str, sources: list[Source], top_k: int) -> list[Source]:
        if not sources:
            return []
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": self.model_name,
            "query": query,
            "documents": [source.content for source in sources],
            "top_n": top_k,
        }
        with httpx.Client(timeout=self.timeout_seconds, headers=headers) as client:
            response = client.post(f"{self.base_url}/rerank", json=payload)
            response.raise_for_status()
        ranked_items = _parse_rerank_response(response.json())
        reranked: list[Source] = []
        for item in ranked_items:
            index = int(item["index"])
            if 0 <= index < len(sources):
                reranked.append(_copy_with_rerank_score(sources[index], "openai_compatible", float(item["score"])))
        return reranked[:top_k]


def create_reranker(provider: str) -> BaseReranker:
    provider = (provider or "mock").lower()
    if provider == "bge":
        try:
            return BGEReranker()
        except Exception:
            return MockReranker()
    if provider == "openai_compatible":
        try:
            return OpenAICompatibleReranker(
                base_url=settings.reranker_base_url,
                api_key=settings.reranker_api_key,
                model_name=settings.reranker_model_name,
                timeout_seconds=settings.reranker_timeout_seconds,
            )
        except Exception:
            return MockReranker()
    return MockReranker()


def _copy_with_rerank_score(source: Source, reranker_type: str, rerank_score: float) -> Source:
    metadata = {
        **source.metadata,
        "original_score": source.score,
        "reranker_type": reranker_type,
        "rerank_score": round(rerank_score, 4),
    }
    return source.model_copy(update={"score": round(rerank_score, 4), "metadata": metadata})


def _parse_rerank_response(payload: dict[str, Any]) -> list[dict[str, float | int]]:
    raw_items = payload.get("results") or payload.get("data") or []
    parsed: list[dict[str, float | int]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        index = item.get("index", item.get("document_index"))
        score = item.get("relevance_score", item.get("score"))
        if index is None or score is None:
            continue
        parsed.append({"index": int(index), "score": float(score)})
    return sorted(parsed, key=lambda item: float(item["score"]), reverse=True)


def _text_terms(text: str) -> set[str]:
    compact = "".join(char for char in text if char.strip())
    terms = set(compact)
    terms.update(compact[index : index + 2] for index in range(max(len(compact) - 1, 0)))
    return terms


def _lexical_similarity(query_terms: set[str], text: str) -> float:
    if not query_terms:
        return 0.0
    text_terms = _text_terms(text)
    return len(query_terms & text_terms) / len(query_terms)
