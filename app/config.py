import os
from dataclasses import dataclass, field


def _split_env(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """集中读取配置，后续接真实 Redis/LLM/Milvus 时不需要改业务代码。"""

    app_name: str = os.getenv("APP_NAME", "Customer Service Agent")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    app_env: str = os.getenv("APP_ENV", "local")
    memory_max_turns: int = int(os.getenv("MEMORY_MAX_TURNS", "8"))
    mock_knowledge_path: str = os.getenv("MOCK_KNOWLEDGE_PATH", "data/mock_knowledge.md")
    knowledge_dir: str = os.getenv("KNOWLEDGE_DIR", "data/knowledge")
    vector_store: str = os.getenv("VECTOR_STORE", "mock")
    vector_store_dir: str = os.getenv("VECTOR_STORE_DIR", "data/vector_store")
    chroma_collection: str = os.getenv("CHROMA_COLLECTION", "customer_service_knowledge")
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "3"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "500"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "80"))
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "mock")
    safety_blocked_words: list[str] = field(
        default_factory=lambda: _split_env(
            "SAFETY_BLOCKED_WORDS",
            "身份证号,银行卡密码,内部系统密码,忽略之前指令,绕过权限",
        )
    )
    output_forbidden_phrases: list[str] = field(
        default_factory=lambda: _split_env(
            "OUTPUT_FORBIDDEN_PHRASES",
            "保证赔偿,一定免费,内部数据,绝对不会",
        )
    )


settings = Settings()
