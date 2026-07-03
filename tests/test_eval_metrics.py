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
