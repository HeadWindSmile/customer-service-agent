import os
from dataclasses import dataclass, field


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _split_env(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """集中读取配置，后续接真实 Redis/LLM/Milvus 时不需要改业务代码。"""

    app_name: str = os.getenv("APP_NAME", "Customer Service Agent")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    app_env: str = os.getenv("APP_ENV", "local")
    memory_backend: str = os.getenv("MEMORY_BACKEND", "memory").lower()
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    memory_ttl_seconds: int = int(os.getenv("MEMORY_TTL_SECONDS", "604800"))
    memory_recent_turns: int = int(os.getenv("MEMORY_RECENT_TURNS", os.getenv("MEMORY_MAX_TURNS", "8")))
    memory_max_turns: int = memory_recent_turns
    mock_knowledge_path: str = os.getenv("MOCK_KNOWLEDGE_PATH", "data/mock_knowledge.md")
    knowledge_dir: str = os.getenv("KNOWLEDGE_DIR", "data/knowledge")
    vector_store: str = os.getenv("VECTOR_STORE", "mock")
    vector_store_dir: str = os.getenv("VECTOR_STORE_DIR", "data/vector_store")
    chroma_collection: str = os.getenv("CHROMA_COLLECTION", "customer_service_knowledge")
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "3"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "500"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "80"))
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "mock")
    embedding_model_name: str = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-v4")
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))
    embedding_timeout_seconds: float = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "10"))
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock").lower()
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")
    dashscope_base_url: str = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    llm_model_name: str = os.getenv("LLM_MODEL_NAME", "qwen-plus")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0"))
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "10"))
    intent_rule_direct_threshold: float = float(os.getenv("INTENT_RULE_DIRECT_THRESHOLD", "0.85"))
    intent_low_confidence_threshold: float = float(os.getenv("INTENT_LOW_CONFIDENCE_THRESHOLD", "0.6"))
    business_service_base_url: str = os.getenv("BUSINESS_SERVICE_BASE_URL", "").strip()
    business_service_timeout_ms: int = int(os.getenv("BUSINESS_SERVICE_TIMEOUT_MS", "800"))
    audit_log_enabled: bool = _env_bool("AUDIT_LOG_ENABLED", "true")
    audit_log_path: str = os.getenv("AUDIT_LOG_PATH", "logs/audit.log")
    event_producer: str = os.getenv("EVENT_PRODUCER", "mock").lower()
    event_log_path: str = os.getenv("EVENT_LOG_PATH", "logs/events.jsonl")
    rocketmq_name_server: str = os.getenv("ROCKETMQ_NAME_SERVER", "")
    rocketmq_topic: str = os.getenv("ROCKETMQ_TOPIC", "customer-service-agent-events")
    trace_enabled: bool = _env_bool("TRACE_ENABLED", "true")
    trace_storage_dir: str = os.getenv("TRACE_STORAGE_DIR", "logs/traces")
    trace_include_raw_content: bool = _env_bool("TRACE_INCLUDE_RAW_CONTENT", "false")
    safety_enabled: bool = _env_bool("SAFETY_ENABLED", "true")
    safety_rules_path: str = os.getenv("SAFETY_RULES_PATH", "config/safety_rules.yml")
    safety_review_queue_path: str = os.getenv("SAFETY_REVIEW_QUEUE_PATH", "logs/review_queue.jsonl")
    safety_semantic_detector: str = os.getenv("SAFETY_SEMANTIC_DETECTOR", "mock").lower()
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
