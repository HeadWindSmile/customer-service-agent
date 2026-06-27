from abc import ABC, abstractmethod
from dataclasses import dataclass

from langchain_core.runnables import Runnable


@dataclass(frozen=True)
class LLMRuntimeConfig:
    """LLM 运行配置。

    这里不直接读取环境变量，避免模型适配层和全局配置耦合；统一由 factory 注入，
    便于测试中构造不同 provider 的降级场景。
    """

    provider: str
    model_name: str
    temperature: float
    timeout_seconds: float
    dashscope_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = ""


class BaseLLMClient(ABC):
    """所有 LLM 适配器都返回 LangChain Runnable，方便 LCEL 链统一编排。"""

    provider: str
    model_name: str

    @abstractmethod
    def as_runnable(self) -> Runnable:
        raise NotImplementedError
