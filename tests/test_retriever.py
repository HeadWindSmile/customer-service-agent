from app.rag.embeddings import MockEmbedding
from app.rag.retriever import KnowledgeRetriever
from app.rag.vector_store import BaseVectorStore, MockVectorStore, create_vector_store


def test_retriever_returns_top_k_sources_with_metadata(tmp_path):
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "fault.md").write_text(
        "# 故障排查\n\n## 宽带无法上网\n宽带连不上时先重启光猫和路由器，再检查欠费状态。",
        encoding="utf-8",
    )
    (knowledge_dir / "billing.md").write_text(
        "# 账单说明\n\n## 超量费用\n账单可能包含套餐月费和超量流量费用。",
        encoding="utf-8",
    )
    vector_store = MockVectorStore(MockEmbedding(), tmp_path / "index.json")
    retriever = KnowledgeRetriever(vector_store=vector_store, knowledge_dir=str(knowledge_dir), top_k=2)

    sources = retriever.search("宽带连不上怎么办", top_k=1)

    assert len(sources) == 1
    assert sources[0].title == "故障排查"
    assert sources[0].metadata["section"] == "宽带无法上网"
    assert sources[0].metadata["chunk_id"]


def test_retriever_handles_empty_knowledge_dir(tmp_path):
    vector_store = MockVectorStore(MockEmbedding(), tmp_path / "index.json")
    retriever = KnowledgeRetriever(vector_store=vector_store, knowledge_dir=str(tmp_path / "missing"), top_k=2)

    assert retriever.search("不存在的问题") == []


def test_chroma_store_falls_back_when_dependency_missing(tmp_path):
    store = create_vector_store("chroma", MockEmbedding(), tmp_path, "test_collection")

    assert isinstance(store, BaseVectorStore)
