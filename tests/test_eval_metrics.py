from evals.metrics import evaluate_case, summarize_results


def test_evaluate_case_checks_intent_keyword_source_tool_and_safety():
    case = {
        "id": "package-query",
        "question": "查询我的当前套餐",
        "expected_intent": "package_query",
        "expected_keywords": ["当前套餐"],
        "expected_tool": "query_user_package",
        "source_required": False,
        "tool_required": True,
        "safety_expected_action": "allow",
    }
    response = {
        "answer": "你当前套餐是 5G畅享套餐。",
        "intent": "package_query",
        "sources": [],
        "tool_calls": [{"tool_name": "query_user_package"}],
        "latency_ms": 12.5,
        "trace_id": "trace-test",
        "safety_result": {"input_safety": {"action": "allow"}},
    }

    result = evaluate_case(case, response)

    assert result["intent_correct"] is True
    assert result["answer_contains_expected_keywords"] is True
    assert result["tool_pass"] is True
    assert result["safety_pass"] is True


def test_summarize_results_outputs_phase10_metrics():
    results = [
        {
            "intent_correct": True,
            "answer_contains_expected_keywords": True,
            "source_required": True,
            "source_pass": True,
            "tool_required": False,
            "tool_pass": True,
            "safety_pass": True,
            "hallucination_flag": False,
            "latency_ms": 10,
        },
        {
            "intent_correct": False,
            "answer_contains_expected_keywords": False,
            "source_required": True,
            "source_pass": False,
            "tool_required": True,
            "tool_pass": False,
            "safety_pass": True,
            "hallucination_flag": True,
            "latency_ms": 30,
        },
    ]

    summary = summarize_results(results)

    assert summary["intent_accuracy"] == 0.5
    assert summary["answer_contains_expected_keywords"] == 0.5
    assert summary["source_recall_rate"] == 0.5
    assert summary["tool_call_accuracy"] == 0.0
    assert summary["safety_expected_action_accuracy"] == 1.0
    assert summary["hallucination_rate"] == 0.5
    assert summary["avg_latency_ms"] == 20


def test_evaluate_case_calculates_phase15_rag_metrics_from_response_and_trace():
    case = {
        "id": "bill-explain-overage",
        "question": "账单里为什么会有超量流量费用？",
        "scenario": "bill_explain",
        "expected_intent": "bill_explain",
        "expected_keywords": ["超量费用"],
        "expected_sources": [
            {
                "doc_id": "billing_policy",
                "title": "账单政策说明",
                "section": "超量费用说明",
                "content_keywords": ["超量费用"],
            }
        ],
        "expected_top_k": 3,
        "expected_rerank": {"reranker_used": True, "top1_doc_id": "billing_policy"},
        "source_required": True,
        "safety_expected_action": "allow",
    }
    response = {
        "answer": "根据知识库《账单政策说明》，超量费用会在超过套餐包含额度时产生。",
        "intent": "bill_explain",
        "sources": [
            {
                "doc_id": "billing_policy",
                "title": "账单政策说明",
                "content": "当用户使用的流量超过套餐包含额度时，可能产生超量费用。",
                "score": 0.98,
                "metadata": {"section": "超量费用说明", "reranker_type": "MockReranker"},
            }
        ],
        "tool_calls": [],
        "latency_ms": 45.0,
        "trace_id": "trace-rag",
        "safety_result": {"input_safety": {"action": "allow"}},
    }
    trace = {
        "attributes": {
            "rag_retrieval_config": {"reranker_used": True, "reranker_type": "MockReranker"},
            "prompt_tokens": 120,
            "completion_tokens": 30,
            "total_tokens": 150,
            "estimated_cost": 0.0003,
            "usage_source": "estimated",
        }
    }

    result = evaluate_case(case, response, trace)

    assert result["top1_hit"] is True
    assert result["top3_hit"] is True
    assert result["topk_hit"] is True
    assert result["source_coverage"] == 1.0
    assert result["rerank_pass"] is True
    assert result["total_tokens"] == 150
    assert result["estimated_cost"] == 0.0003


def test_summarize_results_outputs_phase15_grouped_metrics():
    results = [
        {
            "scenario": "faq",
            "intent_correct": True,
            "answer_contains_expected_keywords": True,
            "source_required": True,
            "source_pass": True,
            "expected_source_count": 1,
            "source_coverage": 1.0,
            "top1_hit": True,
            "top3_hit": True,
            "topk_hit": True,
            "rerank_evaluated": True,
            "rerank_pass": True,
            "tool_required": False,
            "tool_pass": True,
            "safety_pass": True,
            "hallucination_flag": False,
            "latency_ms": 10,
            "prompt_tokens": 20,
            "completion_tokens": 5,
            "total_tokens": 25,
            "estimated_cost": 0.0,
            "usage_source": "estimated",
        },
        {
            "scenario": "tool",
            "intent_correct": True,
            "answer_contains_expected_keywords": True,
            "source_required": False,
            "source_pass": True,
            "expected_source_count": 0,
            "source_coverage": 1.0,
            "top1_hit": False,
            "top3_hit": False,
            "topk_hit": False,
            "rerank_evaluated": False,
            "rerank_pass": True,
            "tool_required": True,
            "tool_pass": True,
            "safety_pass": True,
            "hallucination_flag": False,
            "latency_ms": 30,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost": 0.0,
            "usage_source": "unavailable",
        },
    ]

    summary = summarize_results(results)

    assert summary["top1_hit_rate"] == 1.0
    assert summary["top3_hit_rate"] == 1.0
    assert summary["topk_hit_rate"] == 1.0
    assert summary["source_coverage_avg"] == 1.0
    assert summary["rerank_expectation_accuracy"] == 1.0
    assert summary["tool_call_accuracy"] == 1.0
    assert summary["p95_latency_ms"] == 30
    assert summary["total_tokens"] == 25
    assert set(summary["by_scenario"]) == {"faq", "tool"}
