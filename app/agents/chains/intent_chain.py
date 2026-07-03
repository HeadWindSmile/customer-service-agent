import json
import re
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from app.agents.intent_schema import INTENT_DESCRIPTIONS, SLOT_DESCRIPTIONS, StructuredIntentResult, normalize_intent_name
from app.llm.factory import create_llm_client
from app.observability.llm_usage import record_llm_usage
from app.observability.tracing import end_span, start_span


INTENT_SYSTEM_PROMPT = """你是企业 AI 客服系统的意图识别器。

任务类型：INTENT_CLASSIFICATION_JSON

你只能从以下 intent 中选择一个：
{intent_descriptions}

可抽取 slots：
{slot_descriptions}

要求：
1. 只输出 JSON，不要输出 Markdown、解释或多余文本。
2. JSON 字段必须包含 intent、slots、confidence、reason。
3. confidence 必须是 0 到 1 之间的小数。
4. 如果无法确定意图，intent 使用 unknown，confidence 不要超过 0.59。
5. 不要编造用户没有提供的 ticket_id、手机号、月份或套餐名。
"""

INTENT_USER_PROMPT = """规则预分类结果：
intent={rule_intent}
confidence={rule_confidence}
slots={rule_slots}
reason={rule_reason}

用户问题：
{message}

请输出结构化 JSON。"""


class IntentChain:
    """LLM 结构化意图识别链。

    第四阶段只把 LLM 放在“低确定性意图识别”环节，不让它直接决定业务动作；
    输出还要经过 Pydantic 和 intent 白名单校验，这样 Router 仍然是可控的工程边界。
    """

    def __init__(self, llm: Runnable | None = None) -> None:
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", INTENT_SYSTEM_PROMPT),
                ("human", INTENT_USER_PROMPT),
            ]
        )
        if llm is None:
            llm_client = create_llm_client()
            self.llm = llm_client.as_runnable()
            self.llm_provider = llm_client.provider
            self.model_name = llm_client.model_name
        else:
            self.llm = llm
            self.llm_provider = "custom"
            self.model_name = "custom-runnable"
        self.chain = self.prompt | self.llm | StrOutputParser()

    def classify(
        self,
        message: str,
        rule_intent: str,
        rule_confidence: float,
        rule_slots: dict[str, Any],
        rule_reason: str,
    ) -> StructuredIntentResult:
        inputs = {
            "intent_descriptions": _format_descriptions(INTENT_DESCRIPTIONS),
            "slot_descriptions": _format_descriptions(SLOT_DESCRIPTIONS),
            "rule_intent": rule_intent,
            "rule_confidence": rule_confidence,
            "rule_slots": json.dumps(rule_slots, ensure_ascii=False),
            "rule_reason": rule_reason,
            "message": message,
        }
        llm_span = start_span(
            "llm.generate",
            {
                "stage": "intent_classification",
                "provider": self.llm_provider,
                "model_name": self.model_name,
            },
        )
        try:
            raw_output = self.chain.invoke(inputs)
        except Exception as exc:
            end_span(llm_span, error=str(exc))
            raise
        record_llm_usage(
            provider=self.llm_provider,
            model_name=self.model_name,
            prompt_text=_usage_prompt_text(inputs),
            completion_text=raw_output,
            stage="intent_classification",
        )
        end_span(llm_span)
        payload = _loads_json_object(raw_output)
        payload["intent"] = normalize_intent_name(str(payload.get("intent", "unknown")))
        payload["slots"] = payload.get("slots") or {}
        payload["confidence"] = _safe_confidence(payload.get("confidence"))
        payload["reason"] = str(payload.get("reason", "")).strip()
        return StructuredIntentResult.model_validate(payload)


def _format_descriptions(descriptions: dict[str, str]) -> str:
    return "\n".join(f"- {key}: {value}" for key, value in descriptions.items())


def _loads_json_object(raw_output: str) -> dict[str, Any]:
    """从模型输出中提取 JSON 对象。

    真实模型偶尔会包一层说明文本；这里做最小容错，但仍只接受一个 JSON object，
    防止把任意自然语言当作可信结构进入 Router。
    """

    text = raw_output.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("意图识别结果必须是 JSON object。")
    return parsed


def _safe_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(confidence, 1.0))


def _usage_prompt_text(inputs: dict[str, Any]) -> str:
    """只为 token 粗估拼接，不落盘完整 prompt。"""

    return "\n".join(f"{key}:{value}" for key, value in inputs.items())
