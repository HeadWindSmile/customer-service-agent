import json
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
        if "CONVERSATION_SUMMARY" in prompt_text:
            return _mock_conversation_summary(prompt_text)
        if "INTENT_CLASSIFICATION_JSON" in prompt_text:
            return _mock_intent_json(prompt_text)

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


def _mock_conversation_summary(prompt_text: str) -> str:
    """为 summary buffer 提供稳定输出，避免测试依赖真实 LLM。"""

    existing = _extract_block(prompt_text, "已有摘要：", "新增历史：").strip()
    history = _extract_block(prompt_text, "新增历史：", "输出新的摘要：").strip()
    parts: list[str] = []
    if existing and existing != "无":
        parts.append(existing)
    if history:
        cleaned = re.sub(r"\s+", " ", history)
        parts.append(f"早期对话摘要：{cleaned}")
    summary = "；".join(parts).strip("；")
    if len(summary) > 500:
        return f"{summary[:500]}..."
    return summary or "无"


def _mock_intent_json(prompt_text: str) -> str:
    """为本地 mock 模式提供稳定 JSON，确保没有真实模型也能演示第二阶段链路。"""

    question = _extract_block(prompt_text, "用户问题：", "请输出结构化 JSON").strip()
    slots: dict[str, str] = {}
    ticket_match = re.search(r"(TCK-[A-Za-z0-9]{6,})", question, re.IGNORECASE)
    if ticket_match:
        slots["ticket_id"] = ticket_match.group(1).upper()
    month_match = re.search(r"(20\d{2}[-年]?\d{1,2}|本月|上月)", question)
    if month_match:
        slots["month"] = month_match.group(1).replace("年", "-")

    intent = "unknown"
    confidence = 0.52
    reason = "mock LLM 无法确定意图"

    if _has(question, ["人工客服", "转人工", "真人客服"]):
        intent, confidence, reason = "human_transfer", 0.93, "用户明确要求转人工"
    elif _has(question, ["工单", "TCK-"]) and _has(question, ["查询", "进度", "状态", "查"]):
        intent, confidence, reason = "ticket_query", 0.88, "用户询问工单状态"
    elif _has(question, ["报修", "维修", "上门"]) and _has(question, ["宽带", "网络", "断网"]):
        intent, confidence, reason = "network_repair", 0.88, "用户要求网络报修"
        slots.setdefault("issue_type", "network")
    elif _has(question, ["创建工单", "新建工单", "提交工单", "投诉"]):
        intent, confidence, reason = "ticket_create", 0.87, "用户要求创建工单"
    elif _has(question, ["推荐", "适合", "怎么选", "不够用"]) and _has(question, ["套餐", "流量", "资费"]):
        intent, confidence, reason = "package_recommend", 0.86, "用户需要套餐推荐"
    elif _has(question, ["改套餐", "变更套餐", "升级套餐", "降级套餐", "办理套餐"]):
        intent, confidence, reason = "package_change", 0.9, "用户要求套餐变更"
    elif _has(question, ["当前套餐", "我的套餐", "查套餐"]):
        intent, confidence, reason = "package_query", 0.9, "用户查询当前套餐"
    elif _has(question, ["为什么", "原因", "解释", "怎么算"]) and _has(question, ["账单", "扣费", "费用", "超量"]):
        intent, confidence, reason = "bill_explain", 0.86, "用户需要账单解释"
    elif _has(question, ["账单", "话费", "欠费", "消费明细"]):
        intent, confidence, reason = "bill_query", 0.87, "用户查询账单"
    elif _has(question, ["不能上网", "断网", "没信号", "连不上", "故障"]):
        intent, confidence, reason = "fault_diagnosis", 0.84, "用户询问故障排查"
        slots.setdefault("issue_type", "network")
    elif _has(question, ["规则", "政策", "说明", "是什么", "什么时候", "怎么办"]):
        intent, confidence, reason = "faq_query", 0.75, "用户咨询知识库问题"

    return json.dumps(
        {"intent": intent, "slots": slots, "confidence": confidence, "reason": reason},
        ensure_ascii=False,
    )


def _has(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)
