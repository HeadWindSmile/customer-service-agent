from collections.abc import Sequence
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from app.agents.prompts import NO_SOURCE_ANSWER, RAG_ANSWER_SYSTEM_PROMPT, RAG_ANSWER_USER_PROMPT
from app.llm.factory import create_llm_client
from app.llm.mock_llm import MockLLM
from app.observability.logger import log_event
from app.schemas.chat import Source


class RagAnswerChain:
    """RAG 生成链。

    Router 负责决定是否进入 RAG，Chain 负责把 sources、问题和会话上下文组织成
    LCEL 管道。这样后续替换 Prompt 或模型时，不需要改 intent/router 主分发逻辑。
    """

    def __init__(self, llm: Runnable | None = None) -> None:
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", RAG_ANSWER_SYSTEM_PROMPT),
                ("human", RAG_ANSWER_USER_PROMPT),
            ]
        )
        self.llm = llm or create_llm_client().as_runnable()
        self.fallback_llm = MockLLM().as_runnable()
        self.parser = StrOutputParser()
        self.chain = self.prompt | self.llm | self.parser
        self.fallback_chain = self.prompt | self.fallback_llm | self.parser

    def generate(
        self,
        question: str,
        sources: list[Source],
        conversation_context: Sequence[dict[str, str]] | None = None,
        conversation_summary: str = "",
        key_facts: dict[str, Any] | None = None,
        scenario: str = "faq",
    ) -> str:
        if not sources:
            return NO_SOURCE_ANSWER

        inputs = {
            "question": question,
            "context": _format_sources(sources),
            "conversation_context": _format_memory_context(
                conversation_summary,
                key_facts or {},
                conversation_context or [],
            ),
            "source_titles": "、".join(_unique_source_titles(sources)),
            "scenario": _scenario_instruction(scenario),
        }
        try:
            return self.chain.invoke(inputs).strip()
        except Exception as exc:
            log_event("llm.generate_failed", {"scenario": scenario, "error": str(exc)}, level="error")
            return self.fallback_chain.invoke(inputs).strip()


def _format_sources(sources: list[Source]) -> str:
    rows: list[str] = []
    for index, source in enumerate(sources, start=1):
        section = str(source.metadata.get("section", "")).strip()
        section_line = f"章节：{section}\n" if section else ""
        rows.append(
            f"[{index}] 【来源：{source.title}】\n"
            f"{section_line}"
            f"内容：{source.content.strip()}"
        )
    return "\n\n".join(rows)


def _format_memory_context(
    summary: str,
    key_facts: dict[str, Any],
    turns: Sequence[dict[str, str]],
) -> str:
    lines: list[str] = []
    if summary:
        lines.append(f"历史摘要：{summary}")
    if key_facts:
        facts = "，".join(f"{key}={value}" for key, value in key_facts.items())
        lines.append(f"关键事实：{facts}")
    for turn in turns:
        user = turn.get("user", "").strip()
        assistant = turn.get("assistant", "").strip()
        if user:
            lines.append(f"用户：{user}")
        if assistant:
            lines.append(f"客服：{assistant}")
    return "\n".join(lines) if lines else "无"


def _unique_source_titles(sources: list[Source]) -> list[str]:
    titles: list[str] = []
    for source in sources:
        if source.title and source.title not in titles:
            titles.append(source.title)
    return titles


def _scenario_instruction(scenario: str) -> str:
    if scenario == "fault_diagnosis":
        return "故障排查场景：优先给出可执行排查步骤，资料不足时不要补充未经确认的故障原因，可建议创建售后工单。"
    if scenario == "bill_explain":
        return "账单解释场景：只能解释知识库中的费用规则，具体金额和明细必须以业务系统查询结果为准。"
    if scenario == "package_recommend":
        return "套餐推荐场景：只能基于知识库说明给出选择建议，不要承诺用户一定可办理或一定更优惠。"
    return "知识库咨询场景：直接回答用户问题，保持简洁专业。"
