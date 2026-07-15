import json
import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.config import settings
from app.rag.document import KnowledgeChunk
from app.rag.embeddings import BaseEmbedding, MockEmbedding
from app.schemas.chat import Source


class BaseVectorStore(ABC):
    """向量库抽象层，RAG 链路只依赖这里，便于 mock/Chroma/Milvus 切换。"""

    @abstractmethod
    def add_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, top_k: int) -> list[Source]:
        raise NotImplementedError

    @abstractmethod
    def is_empty(self) -> bool:
        raise NotImplementedError


class MockVectorStore(BaseVectorStore):
    """本地可持久化 mock 向量库，保证不安装 Chroma/Milvus 也能跑完整 RAG。"""

    def __init__(self, embedding: BaseEmbedding | None = None, persist_path: str | Path | None = None) -> None:
        self.embedding = embedding or MockEmbedding()
        self.persist_path = Path(persist_path) if persist_path else None
        self.rows: list[dict[str, Any]] = []
        self._load()

    def add_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        vectors = self.embedding.embed_documents([chunk.content for chunk in chunks])
        self.rows = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            self.rows.append(
                {
                    "id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "content": chunk.content,
                    "source": chunk.source,
                    "section": chunk.section,
                    "metadata": chunk.to_metadata(),
                    "vector": vector,
                }
            )
        self.persist()

    def search(self, query: str, top_k: int) -> list[Source]:
        if not self.rows:
            return []
        query_vector = self.embedding.embed_query(query)
        query_terms = _text_terms(query)
        scored: list[Source] = []
        for row in self.rows:
            vector_score = _cosine_similarity(query_vector, row["vector"])
            lexical_score = _lexical_similarity(query_terms, f"{row['title']} {row['section']} {row['content']}")
            # mock embedding 只负责本地可运行，混合关键词分数能让中文客服短问句更稳定命中文档主题。
            score = vector_score * 0.35 + lexical_score * 0.65
            if score > 0:
                scored.append(
                    Source(
                        doc_id=row["doc_id"],
                        title=row["title"],
                        content=row["content"],
                        score=round(score, 4),
                        metadata=row["metadata"],
                    )
                )
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]

    def is_empty(self) -> bool:
        return not self.rows

    def persist(self) -> None:
        if not self.persist_path:
            return
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        self.persist_path.write_text(json.dumps(self.rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self) -> None:
        if not self.persist_path or not self.persist_path.exists():
            return
        self.rows = json.loads(self.persist_path.read_text(encoding="utf-8"))


class ChromaVectorStore(BaseVectorStore):
    """Chroma 适配层通过 lazy import 实现，避免默认安装路径被重依赖拖住。"""

    def __init__(
        self,
        embedding: BaseEmbedding,
        persist_dir: str | Path,
        collection_name: str,
    ) -> None:
        try:
            import chromadb  # type: ignore
        except ImportError as exc:
            raise RuntimeError("未安装 chromadb，已由调用方回退到 MockVectorStore。") from exc

        self.embedding = embedding
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection = self.client.get_or_create_collection(collection_name)

    def add_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        if not chunks:
            return
        ids = [chunk.chunk_id for chunk in chunks]
        embeddings = self.embedding.embed_documents([chunk.content for chunk in chunks])
        metadatas = [chunk.to_metadata() for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        existing = self.collection.get(ids=ids)
        if existing.get("ids"):
            self.collection.delete(ids=existing["ids"])
        self.collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

    def search(self, query: str, top_k: int) -> list[Source]:
        if self.is_empty():
            return []
        result = self.collection.query(query_embeddings=[self.embedding.embed_query(query)], n_results=top_k)
        sources: list[Source] = []
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for item_id, content, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
            score = 1 / (1 + float(distance))
            sources.append(
                Source(
                    doc_id=str(metadata.get("doc_id", item_id)),
                    title=str(metadata.get("title", "")),
                    content=content,
                    score=round(score, 4),
                    metadata=metadata,
                )
            )
        return sources

    def is_empty(self) -> bool:
        return self.collection.count() == 0


class MilvusVectorStore(BaseVectorStore):
    """Milvus 真实适配层。

    默认本地模式不会强制安装或启动 Milvus；只有 `VECTOR_STORE=milvus` 且
    `MILVUS_URI`、pymilvus 均可用时才连接真实服务，其他情况由工厂回退到 mock。
    """

    def __init__(
        self,
        embedding: BaseEmbedding,
        collection_name: str,
        uri: str,
        token: str = "",
        db_name: str = "",
        timeout_seconds: float = 3,
        metric_type: str = "COSINE",
    ) -> None:
        if not uri:
            raise RuntimeError("MILVUS_URI 未配置，已由调用方回退到 MockVectorStore。")
        try:
            from pymilvus import MilvusClient  # type: ignore
        except ImportError as exc:
            raise RuntimeError("未安装 pymilvus，已由调用方回退到 MockVectorStore。") from exc

        self.embedding = embedding
        self.collection_name = collection_name
        self.metric_type = metric_type.upper()
        client_kwargs: dict[str, Any] = {"uri": uri, "timeout": timeout_seconds}
        if token:
            client_kwargs["token"] = token
        if db_name:
            client_kwargs["db_name"] = db_name
        self.client = MilvusClient(**client_kwargs)

    def add_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        if not chunks:
            return
        vectors = self.embedding.embed_documents([chunk.content for chunk in chunks])
        if not vectors:
            return
        self._ensure_collection(len(vectors[0]))
        rows = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            metadata = chunk.to_metadata()
            rows.append(
                {
                    "id": chunk.chunk_id,
                    "vector": vector,
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "content": chunk.content,
                    "source": chunk.source,
                    "section": chunk.section,
                    "metadata_json": json.dumps(metadata, ensure_ascii=False),
                }
            )
        self.client.upsert(collection_name=self.collection_name, data=rows)

    def search(self, query: str, top_k: int) -> list[Source]:
        if top_k <= 0 or self.is_empty():
            return []
        result = self.client.search(
            collection_name=self.collection_name,
            data=[self.embedding.embed_query(query)],
            anns_field="vector",
            limit=top_k,
            output_fields=["doc_id", "title", "content", "source", "section", "metadata_json"],
        )
        hits = result[0] if result else []
        sources: list[Source] = []
        for hit in hits:
            entity = _hit_entity(hit)
            metadata = _safe_json_loads(str(entity.get("metadata_json") or "{}"))
            score = _milvus_score(hit, self.metric_type)
            sources.append(
                Source(
                    doc_id=str(entity.get("doc_id", _hit_id(hit))),
                    title=str(entity.get("title", "")),
                    content=str(entity.get("content", "")),
                    score=round(score, 4),
                    metadata=metadata,
                )
            )
        return sources

    def is_empty(self) -> bool:
        if not self.client.has_collection(self.collection_name):
            return True
        try:
            stats = self.client.get_collection_stats(self.collection_name)
            return int(stats.get("row_count", 0)) == 0
        except Exception:
            return True

    def _ensure_collection(self, dimension: int) -> None:
        if self.client.has_collection(self.collection_name):
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            dimension=dimension,
            primary_field_name="id",
            id_type="string",
            vector_field_name="vector",
            metric_type=self.metric_type,
            auto_id=False,
            enable_dynamic_field=True,
        )


def create_vector_store(
    store_type: str,
    embedding: BaseEmbedding,
    persist_dir: str | Path,
    collection_name: str,
) -> BaseVectorStore:
    persist_dir = Path(persist_dir)
    if store_type == "chroma":
        try:
            return ChromaVectorStore(embedding, persist_dir / "chroma", collection_name)
        except Exception:
            return MockVectorStore(embedding, persist_dir / "mock_index.json")
    if store_type == "milvus":
        try:
            return MilvusVectorStore(
                embedding=embedding,
                collection_name=settings.milvus_collection or collection_name,
                uri=settings.milvus_uri,
                token=settings.milvus_token,
                db_name=settings.milvus_db_name,
                timeout_seconds=settings.milvus_timeout_seconds,
                metric_type=settings.milvus_metric_type,
            )
        except Exception:
            return MockVectorStore(embedding, persist_dir / "mock_index.json")
    if store_type == "mock":
        return MockVectorStore(embedding, persist_dir / "mock_index.json")
    return MockVectorStore(embedding, persist_dir / "mock_index.json")


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return numerator / (left_norm * right_norm)


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


def _hit_entity(hit: Any) -> dict[str, Any]:
    if isinstance(hit, dict):
        return dict(hit.get("entity") or hit)
    entity = getattr(hit, "entity", None)
    if isinstance(entity, dict):
        return entity
    return {}


def _hit_id(hit: Any) -> str:
    if isinstance(hit, dict):
        return str(hit.get("id", ""))
    return str(getattr(hit, "id", ""))


def _milvus_score(hit: Any, metric_type: str) -> float:
    raw_score = 0.0
    if isinstance(hit, dict):
        raw_score = float(hit.get("distance", hit.get("score", 0.0)))
    else:
        raw_score = float(getattr(hit, "distance", getattr(hit, "score", 0.0)))
    if metric_type in {"COSINE", "IP"}:
        return raw_score
    return 1 / (1 + raw_score)


def _safe_json_loads(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}
