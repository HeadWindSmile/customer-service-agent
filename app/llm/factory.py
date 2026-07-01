from app.config import settings
from app.llm.base import BaseLLMClient, LLMRuntimeConfig
from app.llm.mock_llm import MockLLM
from app.llm.qwen_llm import DashScopeLLM, OpenAICompatibleLLM
from app.observability.logger import log_event


def create_llm_client(config: LLMRuntimeConfig | None = None) -> BaseLLMClient:
    """按配置创建 LLM，并在不可用时降级到 MockLLM。

    外部模型属于非稳定依赖：可能缺少 Key、网络超时或依赖未安装。这里统一兜底，
    可以保证本地 Demo 和自动化测试不被真实模型状态影响。
    """

    runtime_config = config or LLMRuntimeConfig(
        provider=settings.llm_provider,
        model_name=settings.llm_model_name,
        temperature=settings.llm_temperature,
        timeout_seconds=settings.llm_timeout_seconds,
        dashscope_api_key=settings.dashscope_api_key,
        dashscope_base_url=settings.dashscope_base_url,
        openai_api_key=settings.openai_api_key,
        openai_base_url=settings.openai_base_url,
    )
    provider = runtime_config.provider.lower()
    try:
        if provider in {"dashscope", "qwen", "bailian"}:
            return DashScopeLLM(runtime_config)
        if provider == "openai_compatible":
            return OpenAICompatibleLLM(runtime_config)
        if provider != "mock":
            log_event("llm.provider_unknown", {"provider": provider})
        return MockLLM()
    except Exception as exc:
        log_event(
            "llm.fallback_to_mock",
            {"provider": provider, "model_name": runtime_config.model_name, "error": str(exc)},
            level="error",
        )
        return MockLLM()
