from app.llm.base import LLMRuntimeConfig
from app.llm.factory import create_llm_client
from app.llm.mock_llm import MockLLM


def test_llm_factory_uses_mock_by_default_config():
    client = create_llm_client(
        LLMRuntimeConfig(
            provider="mock",
            model_name="qwen-plus",
            temperature=0,
            timeout_seconds=10,
        )
    )

    assert isinstance(client, MockLLM)

def test_llm_factory_falls_back_when_qwen_key_missing():
    client = create_llm_client(
        LLMRuntimeConfig(
            provider="qwen",
            model_name="qwen-plus",
            temperature=0,
            timeout_seconds=10,
            dashscope_api_key="",
        )
    )

    assert isinstance(client, MockLLM)


def test_llm_factory_falls_back_when_openai_compatible_key_missing():
    client = create_llm_client(
        LLMRuntimeConfig(
            provider="openai_compatible",
            model_name="demo-model",
            temperature=0,
            timeout_seconds=10,
            openai_api_key="",
            openai_base_url="https://example.test/v1",
        )
    )

    assert isinstance(client, MockLLM)
