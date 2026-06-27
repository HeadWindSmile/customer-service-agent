from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.rag.embeddings import create_embedding
from app.rag.loader import KnowledgeLoader
from app.rag.splitter import ChineseTextSplitter
from app.rag.vector_store import create_vector_store


def main() -> None:
    """知识库入库入口，串起加载、清洗、分块、embedding 和向量库写入。"""
    loader = KnowledgeLoader(settings.knowledge_dir)
    documents = loader.load()
    splitter = ChineseTextSplitter(settings.chunk_size, settings.chunk_overlap)
    chunks = splitter.split_documents(documents)
    embedding = create_embedding(settings.embedding_provider)
    vector_store = create_vector_store(
        settings.vector_store,
        embedding,
        settings.vector_store_dir,
        settings.chroma_collection,
    )
    vector_store.add_chunks(chunks)
    print(f"ingested_documents={len(documents)} ingested_chunks={len(chunks)} vector_store={settings.vector_store}")


if __name__ == "__main__":
    main()
