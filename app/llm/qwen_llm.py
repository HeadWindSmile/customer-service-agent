from langchain_core.runnables import Runnable

from app.llm.base import BaseLLMClient, LLMRuntimeConfig


QWEN_OPENAI_COMPATIBLE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class OpenAICompatibleLLM(BaseLLMClient):
    """OpenAI-compatible 适配器。

    qwen-plus 的兼容模式和很多企业私有大模型网关都暴露 OpenAI 风格接口，
    统一封装成一个适配器可以减少后续 provider 分支。
    """

    provider = "openai_compatible"

    def __init__(self, config: LLMRuntimeConfig) -> None:
        if not config.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY 未配置，无法创建 OpenAI-compatible LLM。")
        self.model_name = config.model_name
        self.api_key = config.openai_api_key
        self.base_url = config.openai_base_url
        self.temperature = config.temperature
        self.timeout_seconds = config.timeout_seconds

    def as_runnable(self) -> Runnable:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            base_url=self.base_url or None,
            temperature=self.temperature,
            timeout=self.timeout_seconds,
        )


class QwenLLM(OpenAICompatibleLLM):
    """qwen-plus 适配器。

    DashScope 提供 OpenAI-compatible API，本阶段复用 ChatOpenAI 客户端，
    这样既体现真实模型接入点，又避免引入额外重量级 SDK。
    """

    provider = "qwen"

    def __init__(self, config: LLMRuntimeConfig) -> None:
        if not config.dashscope_api_key:
            raise RuntimeError("DASHSCOPE_API_KEY 未配置，无法创建 qwen-plus LLM。")
        qwen_config = LLMRuntimeConfig(
            provider=config.provider,
            model_name=config.model_name or "qwen-plus",
            temperature=config.temperature,
            timeout_seconds=config.timeout_seconds,
            openai_api_key=config.dashscope_api_key,
            openai_base_url=QWEN_OPENAI_COMPATIBLE_BASE_URL,
        )
        super().__init__(qwen_config)
