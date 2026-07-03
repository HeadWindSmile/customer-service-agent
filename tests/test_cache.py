from app.observability.tracing import TraceContext, reset_current_trace, set_current_trace
from app.rag.cache import RagSearchCache, rag_search_cache
from app.rag.retriever import KnowledgeRetriever
from app.schemas.chat import Source


def test_rag_search_cache_returns_copy_and_expires():
    cache = RagSearchCache(ttl_seconds=1, max_size=2)
    source = Source(doc_id="doc-1", title="标题", content="内容", score=0.9, metadata={"section": "A"})

    cache.set("套餐生效", 1, [source])
    cached = cache.get("套餐生效", 1)

    assert cached is not None
    assert cached[0] == source
    assert cached[0] is not source


def test_retriever_records_cache_hit_in_trace():
    rag_search_cache.clear()
    trace = TraceContext.new()
    token = set_current_trace(trace)
    try:
        retriever = KnowledgeRetriever()

        first = retriever.search("套餐变更什么时候生效？", top_k=1)
        assert first
        assert trace.attributes["rag_cache_hit"] is False

        second = retriever.search("套餐变更什么时候生效？", top_k=1)
        assert second
        assert trace.attributes["rag_cache_hit"] is True
        assert any(event.name == "rag.cache_hit" for event in trace.events)
    finally:
        reset_current_trace(token)
