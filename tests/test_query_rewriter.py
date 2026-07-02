from app.agents.query_rewriter import QueryRewriter


def test_rewrite_package_pronoun_with_key_facts():
    result = QueryRewriter().rewrite(
        "这个套餐什么时候生效？",
        key_facts={"target_package": "5G畅享套餐"},
    )

    assert result.changed is True
    assert result.rewritten_query == "5G畅享套餐什么时候生效？"


def test_rewrite_ticket_pronoun_with_key_facts():
    result = QueryRewriter().rewrite(
        "刚才那个工单进度怎么样？",
        key_facts={"last_ticket_id": "TCK-ABC123456"},
    )

    assert result.changed is True
    assert "TCK-ABC123456" in result.rewritten_query


def test_rewrite_bill_pronoun_with_key_facts():
    result = QueryRewriter().rewrite(
        "这笔费用为什么会有超量流量费？",
        key_facts={"last_bill_month": "本月"},
    )

    assert result.changed is True
    assert result.rewritten_query.startswith("本月账单费用")


def test_rewrite_keeps_original_when_reference_is_unknown():
    result = QueryRewriter().rewrite("它怎么样？")

    assert result.changed is False
    assert result.rewritten_query == "它怎么样？"

