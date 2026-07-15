from app.config import settings
from app.rag.embeddings import create_embedding
from app.rag.cache import rag_search_cache
from app.rag.loader import KnowledgeLoader
from app.rag.mmr import select_mmr_sources
from app.rag.reranker import BaseReranker, MockReranker, create_reranker
from app.rag.splitter import ChineseTextSplitter
from app.rag.vector_store import BaseVectorStore, create_vector_store
from app.observability.tracing import add_attribute, add_event
from app.schemas.chat import Source


class KnowledgeRetriever:
    """真实 RAG 检索入口：加载知识库、分块、入库并按 top_k 返回 sources。"""

    def __init__(
        self,
        vector_store: BaseVectorStore | None = None,
        knowledge_dir: str | None = None,
        top_k: int | None = None,
        reranker: BaseReranker | None = None,
    ) -> None:
        self.knowledge_dir = knowledge_dir or settings.knowledge_dir
        self.top_k = top_k or settings.rag_top_k
        self.embedding = create_embedding(settings.embedding_provider)
        self.configured_embedding_provider = settings.embedding_provider
        self.vector_store = vector_store or create_vector_store(
            settings.vector_store,
            self.embedding,
            settings.vector_store_dir,
            settings.chroma_collection,
        )
        self.reranker = reranker or create_reranker(settings.rag_reranker_provider)
        self._ensure_index()

    def search(self, query: str, top_k: int | None = None) -> list[Source]:
        resolved_top_k = top_k or self.top_k
        candidate_top_k = self._candidate_top_k(resolved_top_k)
        cache_variant = self._cache_variant(candidate_top_k)
        if settings.rag_cache_enabled:
            cached = rag_search_cache.get(query, resolved_top_k, variant=cache_variant)
            if cached is not None:
                payload = self._trace_payload(
                    cache_hit=True,
                    top_k=resolved_top_k,
                    candidate_count=len(cached),
                    final_sources=cached,
                    reranker_used=False,
                    reranker_type="cache",
                )
                add_attribute("rag_cache_hit", True)
                self._record_trace(payload)
                add_event("rag.cache_hit", payload)
                return cached

        candidates = self.vector_store.search(query, candidate_top_k)
        sources, reranker_used, reranker_type = self._select_sources(query, candidates, resolved_top_k)
        if settings.rag_cache_enabled:
            rag_search_cache.set(query, resolved_top_k, sources, variant=cache_variant)
        payload = self._trace_payload(
            cache_hit=False,
            top_k=resolved_top_k,
            candidate_count=len(candidates),
            final_sources=sources,
            reranker_used=reranker_used,
            reranker_type=reranker_type,
        )
        add_attribute("rag_cache_hit", False)
        self._record_trace(payload)
        add_event("rag.cache_miss", payload)
        return sources

    def rebuild_index(self) -> int:
        documents = KnowledgeLoader(self.knowledge_dir).load()
        chunks = ChineseTextSplitter(settings.chunk_size, settings.chunk_overlap).split_documents(documents)
        self.vector_store.add_chunks(chunks)
        return len(chunks)

    def _ensure_index(self) -> None:
        if self.vector_store.is_empty():
            self.rebuild_index()

    def _candidate_top_k(self, top_k: int) -> int:
        if settings.rag_mmr_enabled or settings.rag_reranker_enabled:
            return max(top_k, settings.rag_candidate_count)
        return top_k

    def _select_sources(
        self,
        query: str,
        candidates: list[Source],
        top_k: int,
    ) -> tuple[list[Source], bool, str]:
        if not candidates:
            return [], False, type(self.reranker).__name__

        working = candidates
        if settings.rag_mmr_enabled:
            mmr_top_k = top_k
            if settings.rag_reranker_enabled:
                mmr_top_k = min(
                    len(candidates),
                    max(top_k, settings.rag_reranker_candidate_count),
                )
            working = select_mmr_sources(
                query=query,
                candidates=candidates,
                embedding=self.embedding,
                top_k=mmr_top_k,
                lambda_mult=settings.rag_mmr_lambda,
            )

        if not settings.rag_reranker_enabled:
            return working[:top_k], False, "disabled"

        try:
            reranked = self.reranker.rerank(query, working, top_k)
            return reranked[:top_k], True, type(self.reranker).__name__
        except Exception as exc:
            add_event("rag.reranker_failed", {"reranker_type": type(self.reranker).__name__, "error": str(exc)})
            fallback = MockReranker()
            return fallback.rerank(query, working, top_k), True, type(fallback).__name__

    def _trace_payload(
        self,
        *,
        cache_hit: bool,
        top_k: int,
        candidate_count: int,
        final_sources: list[Source],
        reranker_used: bool,
        reranker_type: str,
    ) -> dict[str, object]:
        return {
            "cache_hit": cache_hit,
            "top_k": top_k,
            "candidate_count": candidate_count,
            "source_count": len(final_sources),
            "vector_store_type": type(self.vector_store).__name__,
            "configured_vector_store": settings.vector_store,
            "embedding_provider": type(self.embedding).__name__,
            "configured_embedding_provider": self.configured_embedding_provider,
            "mmr_enabled": settings.rag_mmr_enabled,
            "reranker_used": reranker_used,
            "reranker_type": reranker_type,
            "final_top_k": len(final_sources),
        }

    def _record_trace(self, payload: dict[str, object]) -> None:
        for key in (
            "vector_store_type",
            "embedding_provider",
            "candidate_count",
            "mmr_enabled",
            "reranker_used",
            "reranker_type",
            "final_top_k",
        ):
            add_attribute(key, payload[key])
        add_attribute("rag_retrieval_config", payload)

    def _cache_variant(self, candidate_top_k: int) -> str:
        return "|".join(
            [
                f"store={settings.vector_store}",
                f"embedding={settings.embedding_provider}",
                f"candidate={candidate_top_k}",
                f"mmr={settings.rag_mmr_enabled}:{settings.rag_mmr_lambda}",
                f"reranker={settings.rag_reranker_enabled}:{settings.rag_reranker_provider}",
            ]
        )


# 保留旧类名作为兼容入口，避免第一阶段调用方或测试需要大规模调整。
MockKnowledgeRetriever = KnowledgeRetriever
