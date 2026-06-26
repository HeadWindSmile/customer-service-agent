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

