import pytest

from app.agents.intent_classifier import IntentClassifier
from app.agents.intent_schema import IntentName, StructuredIntentResult


class StubIntentChain:
    def __init__(self, result: StructuredIntentResult | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.called = False

    def classify(self, **kwargs):
        self.called = True
        if self.error:
            raise self.error
        return self.result


@pytest.mark.parametrize(
    ("message", "expected_intent"),
    [
        ("套餐变更什么时候生效？", IntentName.FAQ_QUERY.value),
        ("查询我的当前套餐", IntentName.PACKAGE_QUERY.value),
        ("我流量经常不够，推荐一个适合的套餐", IntentName.PACKAGE_RECOMMEND.value),
        ("我要办理5G畅享套餐", IntentName.PACKAGE_CHANGE.value),
        ("帮我查本月账单", IntentName.BILL_QUERY.value),
        ("账单里为什么会有超量流量费用？", IntentName.BILL_EXPLAIN.value),
        ("宽带连不上应该怎么排查？", IntentName.FAULT_DIAGNOSIS.value),
        ("我要报修宽带断网", IntentName.NETWORK_REPAIR.value),
        ("我要创建工单，宽带断网", IntentName.TICKET_CREATE.value),
        ("帮我查工单 TCK-ABC123456 的进度", IntentName.TICKET_QUERY.value),
        ("帮我转人工客服", IntentName.HUMAN_TRANSFER.value),
    ],
)
def test_rule_classifier_supports_12_intent_taxonomy(message: str, expected_intent: str):
    classifier = IntentClassifier()

    result = classifier.classify(message)

    assert result.intent == expected_intent
    assert result.confidence >= 0.6
    assert result.reason


def test_low_certainty_rule_uses_llm_structured_result():
    chain = StubIntentChain(
        StructuredIntentResult(
            intent=IntentName.PACKAGE_RECOMMEND,
            slots={"product_name": "套餐"},
            confidence=0.82,
            reason="用户在表达选择套餐诉求",
        )
    )
    classifier = IntentClassifier(intent_chain=chain)

    result = classifier.classify("帮我看看这个资费怎么处理")

    assert chain.called is True
    assert result.intent == "package_recommend"
    assert result.slots["product_name"] == "套餐"
    assert result.confidence == 0.82


def test_llm_failure_falls_back_to_rule_result():
    chain = StubIntentChain(error=RuntimeError("llm timeout"))
    classifier = IntentClassifier(intent_chain=chain)

    result = classifier.classify("帮我看看这个事情")

    assert chain.called is True
    assert result.intent == "unknown"
    assert result.confidence < 0.6


def test_common_slots_are_extracted_before_llm_stage():
    classifier = IntentClassifier()

    result = classifier.classify("帮用户u1002查工单 TCK-ABC123456 的进度，手机号 13812345678")

    assert result.intent == "ticket_query"
    assert result.slots["target_user_id"] == "u1002"
    assert result.slots["ticket_id"] == "TCK-ABC123456"
    assert result.slots["phone_number"] == "138****5678"
