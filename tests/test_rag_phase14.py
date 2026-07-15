import sys
from types import SimpleNamespace

from app.observability.tracing import TraceContext, reset_current_trace, set_current_trace
from app.rag.embeddings import BaseEmbedding, MockEmbedding, create_embedding
from app.rag.mmr import select_mmr_sources
from app.rag.reranker import MockReranker, create_reranker
from app.rag.retriever import KnowledgeRetriever
from app.rag.splitter import ChineseTextSplitter
from app.rag import vector_store as vector_store_module
from app.rag.vector_store import MockVectorStore, create_vector_store
from app.rag.cache import rag_search_cache
from app.rag.document import KnowledgeDocument
from app.schemas.chat import Source


def test_chinese_splitter_keeps_sentence_separator_and_metadata():
    document = KnowledgeDocument(
        doc_id="policy",
        title="客服规则",
        content="# 客服规则\n\n## 生效规则\n第一句。第二句！第三句？第四句；",
        source="data/knowledge/policy.md",
        metadata={"filename": "policy.md"},
    )

    chunks = ChineseTextSplitter(chunk_size=7, chunk_overlap=0).split_document(document)

    assert [chunk.section for chunk in chunks] == ["生效规则", "生效规则", "生效规则", "生效规则"]
    assert chunks[0].content.endswith("。")
    assert chunks[1].content.endswith("！")
    assert chunks[2].content.endswith("？")
    assert chunks[3].content.endswith("；")
    assert all(not chunk.content.startswith(("。", "！", "？", "；")) for chunk in chunks)
    assert chunks[0].metadata["filename"] == "policy.md"
    assert chunks[0].source == "data/knowledge/policy.md"


def test_mmr_selects_relevant_and_diverse_sources():
    class StaticEmbedding(BaseEmbedding):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            vectors = []
            for text in texts:
                if "重复候选" in text:
                    vectors.append([0.98, 0.02])
                elif "多样候选" in text:
                    vectors.append([0.6, 0.8])
                else:
                    vectors.append([1.0, 0.0])
            return vectors

        def embed_query(self, text: str) -> list[float]:
            return [1.0, 0.0]

    sources = [
        Source(doc_id="main", title="主候选", content="宽带断网排查", score=0.99, metadata={}),
        Source(doc_id="duplicate", title="重复候选", content="宽带断网排查重复", score=0.98, metadata={}),
        Source(doc_id="diverse", title="多样候选", content="WiFi 信号覆盖排查", score=0.8, metadata={}),
    ]

    selected = select_mmr_sources("宽带断网", sources, StaticEmbedding(), top_k=2, lambda_mult=0.2)

    assert [source.doc_id for source in selected] == ["main", "diverse"]
    assert selected[0].metadata["mmr_rank"] == 1
    assert "mmr_query_score" in selected[1].metadata


def test_mock_reranker_prefers_lexically_relevant_source():
    sources = [
        Source(doc_id="fault", title="故障说明", content="宽带断网时重启光猫。", score=0.5, metadata={}),
        Source(doc_id="billing", title="账单说明", content="超量流量费用会计入当月账单。", score=0.5, metadata={}),
    ]

    reranked = MockReranker().rerank("为什么有超量流量费用", sources, top_k=1)

    assert reranked[0].doc_id == "billing"
    assert reranked[0].metadata["reranker_type"] == "mock"
    assert reranked[0].metadata["original_score"] == 0.5


def test_bge_embedding_provider_falls_back_without_dependency(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)

    embedding = create_embedding("bge")

    assert isinstance(embedding, MockEmbedding)


def test_bge_reranker_provider_falls_back_without_dependency(monkeypatch):
    monkeypatch.setitem(sys.modules, "FlagEmbedding", None)

    reranker = create_reranker("bge")

    assert isinstance(reranker, MockReranker)


def test_milvus_store_falls_back_when_not_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(
        vector_store_module,
        "settings",
        SimpleNamespace(
            milvus_collection="test_collection",
            milvus_uri="",
            milvus_token="",
            milvus_db_name="",
            milvus_timeout_seconds=1,
            milvus_metric_type="COSINE",
        ),
    )

    store = create_vector_store("milvus", MockEmbedding(), tmp_path, "test_collection")

    assert isinstance(store, MockVectorStore)


def test_retriever_records_phase14_trace_fields(tmp_path):
    rag_search_cache.clear()
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "fault.md").write_text(
        "# 故障排查\n\n## 宽带无法上网\n宽带断网时先重启光猫，再检查路由器和欠费状态。",
        encoding="utf-8",
    )
    vector_store = MockVectorStore(MockEmbedding(), tmp_path / "index.json")
    trace = TraceContext.new()
    token = set_current_trace(trace)

    try:
        retriever = KnowledgeRetriever(vector_store=vector_store, knowledge_dir=str(knowledge_dir), top_k=2)
        sources = retriever.search("第十四阶段宽带断网排查", top_k=1)
    finally:
        reset_current_trace(token)

    assert sources
    assert trace.attributes["vector_store_type"] == "MockVectorStore"
    assert trace.attributes["embedding_provider"] == "MockEmbedding"
    assert trace.attributes["candidate_count"] >= 1
    assert trace.attributes["mmr_enabled"] is True
    assert trace.attributes["reranker_used"] is True
    assert trace.attributes["reranker_type"] == "MockReranker"
    assert trace.attributes["final_top_k"] == len(sources)
    assert trace.attributes["rag_retrieval_config"]["candidate_count"] >= 1
