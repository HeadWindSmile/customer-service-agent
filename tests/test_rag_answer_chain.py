from langchain_core.runnables import RunnableLambda

from app.agents.chains.rag_answer_chain import RagAnswerChain
from app.agents.prompts import NO_SOURCE_ANSWER
from app.llm.mock_llm import MockLLM
from app.schemas.chat import Source


def make_source() -> Source:
    return Source(
        doc_id="package_policy",
        title="套餐政策说明",
        content="套餐变更通常在次月生效，办理结果以业务系统记录为准。",
        score=0.91,
        metadata={"section": "套餐变更生效规则"},
    )


def test_rag_answer_chain_generates_answer_with_source_title():
    chain = RagAnswerChain(llm=MockLLM().as_runnable())

    answer = chain.generate(
        question="套餐变更什么时候生效？",
        sources=[make_source()],
        conversation_context=[{"user": "我想了解套餐", "assistant": "可以，我来查询知识库。"}],
    )

    assert "根据知识库《套餐政策说明》" in answer
    assert "次月生效" in answer


def test_rag_answer_chain_does_not_generate_without_sources():
    chain = RagAnswerChain(llm=MockLLM().as_runnable())

    answer = chain.generate(question="不存在的问题", sources=[])

    assert answer == NO_SOURCE_ANSWER


def test_rag_answer_chain_falls_back_to_mock_when_llm_fails():
    failing_llm = RunnableLambda(lambda _: (_ for _ in ()).throw(RuntimeError("llm timeout")))
    chain = RagAnswerChain(llm=failing_llm)

    answer = chain.generate(question="套餐变更什么时候生效？", sources=[make_source()])

    assert "根据知识库《套餐政策说明》" in answer
