from app.rag.embeddings import MockEmbedding
from app.rag.loader import KnowledgeLoader
from app.rag.splitter import ChineseTextSplitter
from app.rag.vector_store import MockVectorStore


def test_load_clean_split_and_store_knowledge(tmp_path):
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "package_policy.md").write_text(
        "# 套餐政策\n\n## 生效规则\n\n套餐变更通常次月生效。\n\n\n办理结果以业务系统为准。",
        encoding="utf-8",
    )

    documents = KnowledgeLoader(knowledge_dir).load()
    chunks = ChineseTextSplitter(chunk_size=30, chunk_overlap=5).split_documents(documents)
    vector_store = MockVectorStore(MockEmbedding(), tmp_path / "mock_index.json")
    vector_store.add_chunks(chunks)

    assert len(documents) == 1
    assert chunks
    assert chunks[0].section == "生效规则"
    assert chunks[0].metadata["filename"] == "package_policy.md"
    assert not vector_store.is_empty()
    assert (tmp_path / "mock_index.json").exists()


def test_loader_supports_txt_files(tmp_path):
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "billing.txt").write_text("账单说明\n账单包括套餐月费和超量费用。", encoding="utf-8")

    documents = KnowledgeLoader(knowledge_dir).load()

    assert len(documents) == 1
    assert documents[0].metadata["suffix"] == ".txt"
    assert "超量费用" in documents[0].content
