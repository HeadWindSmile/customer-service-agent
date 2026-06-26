from abc import ABC, abstractmethod

from app.rag.document import KnowledgeDocument
from app.schemas.chat import Source


class BaseVectorStore(ABC):
    """向量库抽象层，第一阶段用 mock，第二阶段可替换 Chroma/Milvus。"""

    @abstractmethod
    def search(self, query: str, top_k: int) -> list[Source]:
        raise NotImplementedError


class MockVectorStore(BaseVectorStore):
    """关键词打分版本，用来保证本地不依赖 Milvus 也能演示 sources 返回。"""

    def __init__(self, documents: list[KnowledgeDocument]) -> None:
        self.documents = documents

    def search(self, query: str, top_k: int) -> list[Source]:
        query_terms = {char for char in query if char.strip()}
        scored: list[Source] = []
        for doc in self.documents:
            doc_terms = {char for char in doc.title + doc.content if char.strip()}
            overlap = len(query_terms & doc_terms)
            score = overlap / max(len(query_terms), 1)
            if score > 0:
                scored.append(
                    Source(
                        doc_id=doc.doc_id,
                        title=doc.title,
                        content=doc.content,
                        score=round(score, 4),
                    )
                )
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]


class MilvusVectorStore(BaseVectorStore):
    """Milvus 适配层占位，避免第一阶段引入重依赖，同时保留生产扩展方向。"""

    def search(self, query: str, top_k: int) -> list[Source]:
        raise NotImplementedError("第 1 阶段不接入真实 Milvus，请使用 MockVectorStore。")

