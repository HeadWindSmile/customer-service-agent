from app.config import settings
from app.rag.embeddings import create_embedding
from app.rag.loader import KnowledgeLoader
from app.rag.splitter import ChineseTextSplitter
from app.rag.vector_store import BaseVectorStore, create_vector_store
from app.schemas.chat import Source


class KnowledgeRetriever:
    """真实 RAG 检索入口：加载知识库、分块、入库并按 top_k 返回 sources。"""

    def __init__(
        self,
        vector_store: BaseVectorStore | None = None,
        knowledge_dir: str | None = None,
        top_k: int | None = None,
    ) -> None:
        self.knowledge_dir = knowledge_dir or settings.knowledge_dir
        self.top_k = top_k or settings.rag_top_k
        self.embedding = create_embedding(settings.embedding_provider)
        self.vector_store = vector_store or create_vector_store(
            settings.vector_store,
            self.embedding,
            settings.vector_store_dir,
            settings.chroma_collection,
        )
        self._ensure_index()

    def search(self, query: str, top_k: int = 3) -> list[Source]:
        return self.vector_store.search(query, top_k or self.top_k)

    def rebuild_index(self) -> int:
        documents = KnowledgeLoader(self.knowledge_dir).load()
        chunks = ChineseTextSplitter(settings.chunk_size, settings.chunk_overlap).split_documents(documents)
        self.vector_store.add_chunks(chunks)
        return len(chunks)

    def _ensure_index(self) -> None:
        if self.vector_store.is_empty():
            self.rebuild_index()


# 保留旧类名作为兼容入口，避免第一阶段调用方或测试需要大规模调整。
MockKnowledgeRetriever = KnowledgeRetriever
