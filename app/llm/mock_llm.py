import re
from typing import Any

from langchain_core.runnables import Runnable, RunnableLambda

from app.config import settings
from app.llm.base import BaseLLMClient


class MockLLM(BaseLLMClient):
    """本地 mock LLM。

    mock 的目标不是模拟模型智力，而是保证没有 API Key、没有外网时仍能跑通
    “Prompt -> LLM -> Parser” 的 LCEL 形态，并让测试输出稳定可断言。
    """

    provider = "mock"
    model_name = "mock-customer-service-llm"

    def as_runnable(self) -> Runnable:
        return RunnableLambda(self.invoke)

    def invoke(self, prompt_input: Any) -> str:
        prompt_text = _prompt_to_text(prompt_input)
        context = _extract_block(prompt_text, "知识库资料：", "用户问题：")
        question = _extract_block(prompt_text, "用户问题：", "回答场景：").strip()
        scenario = _extract_block(prompt_text, "回答场景：", "来源标题：").strip()
        titles = _extract_titles(prompt_text)

        if not context.strip() or context.strip() in {"无", "（无）"}:
            return "根据当前知识库无法确认，建议转人工客服。"

        first_title = titles[0] if titles else "知识库资料"
        summary = _summarize_context(context)
        if "故障" in scenario or "排查" in scenario:
            return (
                f"根据知识库《{first_title}》，建议先按资料中的步骤排查：{summary}"
                " 如果仍未恢复，建议创建售后工单由人工客服继续处理。"
            )
        return (
            f"根据知识库《{first_title}》，{summary}"
            " 具体办理或账单结果请以业务系统记录为准。"
        )


def _prompt_to_text(prompt_input: Any) -> str:
    if hasattr(prompt_input, "to_string"):
        return prompt_input.to_string()
    if hasattr(prompt_input, "messages"):
        return "\n".join(str(message.content) for message in prompt_input.messages)
    return str(prompt_input)


def _extract_block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        return ""
    start += len(start_marker)
    end = text.find(end_marker, start)
    if end == -1:
        return text[start:]
    return text[start:end]


def _extract_titles(text: str) -> list[str]:
    marker = "来源标题："
    start = text.find(marker)
    if start != -1:
        line = text[start + len(marker) :].splitlines()[0]
        titles = [item.strip() for item in re.split(r"[、,，]", line) if item.strip()]
        if titles:
            return titles
    return re.findall(r"【来源：([^】]+)】", text)


def _summarize_context(context: str, max_length: int = 180) -> str:
    first_source_block = context.split("\n\n", 1)[0]
    cleaned_lines: list[str] = []
    for line in first_source_block.splitlines():
        line = re.sub(r"^\[\d+\]\s*", "", line).strip()
        line = re.sub(r"^【来源：[^】]+】", "", line).strip()
        line = re.sub(r"^章节：.*$", "", line).strip()
        if line and not line.startswith("内容："):
            cleaned_lines.append(line)
        elif line.startswith("内容："):
            cleaned_lines.append(line.removeprefix("内容：").strip())
    summary = " ".join(cleaned_lines).strip()
    summary = _sanitize_forbidden_phrases(summary)
    if len(summary) > max_length:
        return f"{summary[:max_length]}..."
    return summary


def _sanitize_forbidden_phrases(text: str) -> str:
    sanitized = text
    for phrase in settings.output_forbidden_phrases:
        if phrase:
            sanitized = sanitized.replace(phrase, "未经确认的服务承诺")
    return sanitized
