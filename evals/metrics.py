from typing import Any, Callable

from evals.schema import normalize_case


def evaluate_case(
    case: dict[str, Any],
    response: dict[str, Any],
    trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """评估单条用例。

    第 15 阶段优先复用 `/api/chat` 响应；如果 runner 拉到了 trace，则补充
    rerank、token/cost 等观测字段。trace 不可用时仍能生成 response-only 报告。
    """

    normalized_case = normalize_case(case)
    expected_tool = normalized_case.get("expected_tool")
    expected_keywords = normalized_case.get("expected_keywords") or []
    expected_sources = normalized_case.get("expected_sources") or []
    expected_top_k = int(normalized_case.get("expected_top_k") or 3)
    expected_rerank = normalized_case.get("expected_rerank") or {}
    forbidden_answer_keywords = normalized_case.get("forbidden_answer_keywords") or []

    sources = _response_sources(response)
    tool_calls = response.get("tool_calls", []) or []
    tool_names = [call.get("tool_name") for call in tool_calls]
    answer = str(response.get("answer", ""))
    safety_action = _extract_safety_action(response)
    usage = _extract_usage(response, trace)

    source_required = bool(normalized_case.get("source_required", normalized_case.get("should_have_sources", False)))
    tool_required = bool(normalized_case.get("tool_required", bool(expected_tool)))
    keywords_hit = all(keyword in answer for keyword in expected_keywords)
    forbidden_hits = [keyword for keyword in forbidden_answer_keywords if keyword and keyword in answer]
    source_coverage = _source_coverage(expected_sources, sources, expected_top_k)
    source_pass = _source_pass(source_required, expected_sources, sources, source_coverage)
    tool_pass = _tool_pass(
        tool_required=tool_required,
        expected_tool=expected_tool,
        expected_tool_success=normalized_case.get("expected_tool_success"),
        tool_calls=tool_calls,
        tool_names=tool_names,
    )
    safety_pass = _matches_safety_action(normalized_case.get("safety_expected_action", "allow"), safety_action)
    rerank_result = _evaluate_rerank(expected_rerank, sources, trace)

    hallucination_flag = bool(
        (source_required and not sources)
        or (expected_sources and source_coverage == 0)
        or (source_required and not keywords_hit)
        or forbidden_hits
    )

    return {
        "case_id": normalized_case.get("id"),
        "question": normalized_case.get("question"),
        "scenario": normalized_case.get("scenario"),
        "tags": normalized_case.get("tags", []),
        "intent": response.get("intent"),
        "expected_intent": normalized_case.get("expected_intent"),
        "intent_correct": response.get("intent") == normalized_case.get("expected_intent"),
        "answer_contains_expected_keywords": keywords_hit,
        "expected_keywords": expected_keywords,
        "forbidden_answer_keywords_hit": forbidden_hits,
        "expected_source_count": len(expected_sources),
        "source_required": source_required,
        "source_pass": source_pass,
        "source_coverage": source_coverage,
        "top1_hit": _source_hit_at_k(expected_sources, sources, 1),
        "top3_hit": _source_hit_at_k(expected_sources, sources, 3),
        "topk_hit": _source_hit_at_k(expected_sources, sources, expected_top_k),
        "expected_top_k": expected_top_k,
        "actual_source_count": len(sources),
        "source_doc_ids": [_source_value(source, "doc_id") for source in sources],
        "source_scores": [_safe_float(source.get("score")) for source in sources],
        "tool_required": tool_required,
        "expected_tool": expected_tool,
        "expected_tool_success": normalized_case.get("expected_tool_success"),
        "tool_names": tool_names,
        "tool_pass": tool_pass,
        "safety_expected_action": normalized_case.get("safety_expected_action", "allow"),
        "safety_action": safety_action,
        "safety_pass": safety_pass,
        "latency_ms": float(response.get("latency_ms") or 0),
        "trace_id": response.get("trace_id"),
        "trace_loaded": trace is not None,
        "hallucination_flag": hallucination_flag,
        "error": response.get("error"),
        **rerank_result,
        **usage,
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _summarize_core(results)
    summary["by_scenario"] = {
        scenario: _summarize_core([item for item in results if item.get("scenario") == scenario])
        for scenario in sorted({str(item.get("scenario") or "unknown") for item in results})
    }
    return summary


def _summarize_core(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    if total == 0:
        return {
            "total_cases": 0,
            "intent_accuracy": 0.0,
            "answer_contains_expected_keywords": 0.0,
            "source_recall_rate": 0.0,
            "source_coverage_avg": 0.0,
            "top1_hit_rate": 0.0,
            "top3_hit_rate": 0.0,
            "topk_hit_rate": 0.0,
            "topk_evaluated_cases": 0,
            "rerank_expectation_accuracy": 0.0,
            "rerank_evaluated_cases": 0,
            "tool_call_accuracy": 0.0,
            "safety_expected_action_accuracy": 0.0,
            "safety_action_accuracy": 0.0,
            "hallucination_rate": 0.0,
            "avg_latency_ms": 0.0,
            "p50_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "max_latency_ms": 0.0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "avg_tokens_per_case": 0.0,
            "total_estimated_cost": 0.0,
            "usage_sources": [],
        }

    source_scoped = [item for item in results if item.get("expected_source_count", 0) > 0]
    rerank_scoped = [item for item in results if item.get("rerank_evaluated")]
    latencies = [float(item.get("latency_ms") or 0) for item in results]
    total_prompt_tokens = sum(int(item.get("prompt_tokens") or 0) for item in results)
    total_completion_tokens = sum(int(item.get("completion_tokens") or 0) for item in results)
    total_tokens = sum(int(item.get("total_tokens") or 0) for item in results)
    total_estimated_cost = round(sum(float(item.get("estimated_cost") or 0.0) for item in results), 6)
    safety_accuracy = _ratio(results, "safety_pass")

    return {
        "total_cases": total,
        "intent_accuracy": _ratio(results, "intent_correct"),
        "answer_contains_expected_keywords": _ratio(results, "answer_contains_expected_keywords"),
        "source_recall_rate": _conditional_ratio(results, lambda item: bool(item.get("source_required")), "source_pass"),
        "source_coverage_avg": _avg([float(item.get("source_coverage") or 0) for item in source_scoped]),
        "top1_hit_rate": _conditional_ratio(
            results,
            lambda item: item.get("expected_source_count", 0) > 0,
            "top1_hit",
            empty_value=0.0,
        ),
        "top3_hit_rate": _conditional_ratio(
            results,
            lambda item: item.get("expected_source_count", 0) > 0,
            "top3_hit",
            empty_value=0.0,
        ),
        "topk_hit_rate": _conditional_ratio(
            results,
            lambda item: item.get("expected_source_count", 0) > 0,
            "topk_hit",
            empty_value=0.0,
        ),
        "topk_evaluated_cases": len(source_scoped),
        "rerank_expectation_accuracy": _ratio(rerank_scoped, "rerank_pass") if rerank_scoped else 0.0,
        "rerank_evaluated_cases": len(rerank_scoped),
        "tool_call_accuracy": _conditional_ratio(results, lambda item: bool(item.get("tool_required")), "tool_pass"),
        "safety_expected_action_accuracy": safety_accuracy,
        "safety_action_accuracy": safety_accuracy,
        "hallucination_rate": round(sum(1 for item in results if item.get("hallucination_flag")) / total, 4),
        "avg_latency_ms": _avg(latencies),
        "p50_latency_ms": _percentile(latencies, 50),
        "p95_latency_ms": _percentile(latencies, 95),
        "max_latency_ms": round(max(latencies), 2) if latencies else 0.0,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "avg_tokens_per_case": round(total_tokens / total, 2),
        "total_estimated_cost": total_estimated_cost,
        "usage_sources": sorted({str(item.get("usage_source") or "unavailable") for item in results}),
    }


def _response_sources(response: dict[str, Any]) -> list[dict[str, Any]]:
    sources = response.get("sources") or []
    return [source for source in sources if isinstance(source, dict)]


def _source_pass(
    source_required: bool,
    expected_sources: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    source_coverage: float,
) -> bool:
    if not source_required:
        return True
    if expected_sources:
        return source_coverage > 0
    return bool(sources)


def _source_hit_at_k(expected_sources: list[dict[str, Any]], sources: list[dict[str, Any]], top_k: int) -> bool:
    if not expected_sources:
        return False
    selected = sources[: max(1, top_k)]
    return any(_matches_expected_source(expected, source) for expected in expected_sources for source in selected)


def _source_coverage(expected_sources: list[dict[str, Any]], sources: list[dict[str, Any]], top_k: int) -> float:
    if not expected_sources:
        return 1.0
    selected = sources[: max(1, top_k)]
    hit_count = sum(
        1 for expected in expected_sources if any(_matches_expected_source(expected, source) for source in selected)
    )
    return round(hit_count / len(expected_sources), 4)


def _matches_expected_source(expected: dict[str, Any], source: dict[str, Any]) -> bool:
    checks: list[bool] = []
    expected_doc_id = str(expected.get("doc_id") or "").strip()
    if expected_doc_id:
        checks.append(expected_doc_id == _source_value(source, "doc_id"))
    expected_title = str(expected.get("title") or "").strip()
    if expected_title:
        actual_title = _source_value(source, "title")
        checks.append(expected_title == actual_title or expected_title in actual_title)
    expected_section = str(expected.get("section") or "").strip()
    if expected_section:
        actual_section = str((source.get("metadata") or {}).get("section") or "")
        checks.append(expected_section == actual_section or expected_section in actual_section)
    content_keywords = expected.get("content_keywords") or []
    if content_keywords:
        content = str(source.get("content") or "")
        checks.append(all(keyword in content for keyword in content_keywords))
    return bool(checks) and all(checks)


def _source_value(source: dict[str, Any], key: str) -> str:
    value = source.get(key)
    if value not in (None, ""):
        return str(value)
    metadata = source.get("metadata") or {}
    return str(metadata.get(key) or "")


def _tool_pass(
    *,
    tool_required: bool,
    expected_tool: str | None,
    expected_tool_success: bool | None,
    tool_calls: list[dict[str, Any]],
    tool_names: list[str | None],
) -> bool:
    if not tool_required:
        return not tool_names
    if expected_tool:
        matched_calls = [call for call in tool_calls if call.get("tool_name") == expected_tool]
        if not matched_calls:
            return False
    else:
        matched_calls = tool_calls
        if not matched_calls:
            return False
    if expected_tool_success is None:
        return True
    return any(
        "success" not in call or bool(call.get("success")) is bool(expected_tool_success)
        for call in matched_calls
    )


def _evaluate_rerank(
    expected_rerank: dict[str, Any],
    sources: list[dict[str, Any]],
    trace: dict[str, Any] | None,
) -> dict[str, Any]:
    if not expected_rerank:
        return {
            "rerank_evaluated": False,
            "rerank_pass": True,
            "reranker_used": _actual_reranker_used(sources, trace),
            "reranker_type": _actual_reranker_type(sources, trace),
            "rag_cache_hit": _rag_cache_hit(trace),
        }

    actual_used = _actual_reranker_used(sources, trace)
    actual_type = _actual_reranker_type(sources, trace)
    checks: list[bool] = []
    if "reranker_used" in expected_rerank:
        checks.append(actual_used is bool(expected_rerank["reranker_used"]))
    if expected_rerank.get("reranker_type"):
        checks.append(str(expected_rerank["reranker_type"]) == actual_type)
    if expected_rerank.get("top1_doc_id"):
        checks.append(bool(sources) and _source_value(sources[0], "doc_id") == str(expected_rerank["top1_doc_id"]))
    return {
        "rerank_evaluated": True,
        "rerank_pass": bool(checks) and all(checks),
        "reranker_used": actual_used,
        "reranker_type": actual_type,
        "rag_cache_hit": _rag_cache_hit(trace),
    }


def _trace_attributes(trace: dict[str, Any] | None) -> dict[str, Any]:
    if not trace:
        return {}
    attrs = trace.get("attributes") if isinstance(trace, dict) else {}
    return attrs if isinstance(attrs, dict) else {}


def _rag_config(trace: dict[str, Any] | None) -> dict[str, Any]:
    attrs = _trace_attributes(trace)
    for key in ("rag_retrieval_config", "rag_retrieval"):
        value = attrs.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _actual_reranker_used(sources: list[dict[str, Any]], trace: dict[str, Any] | None) -> bool:
    config = _rag_config(trace)
    if config.get("reranker_used") is True or _trace_attributes(trace).get("reranker_used") is True:
        return True
    return any(bool((source.get("metadata") or {}).get("reranker_type")) for source in sources)


def _actual_reranker_type(sources: list[dict[str, Any]], trace: dict[str, Any] | None) -> str:
    config = _rag_config(trace)
    value = config.get("reranker_type") or _trace_attributes(trace).get("reranker_type")
    if value and value != "cache":
        return str(value)
    for source in sources:
        reranker_type = (source.get("metadata") or {}).get("reranker_type")
        if reranker_type:
            return str(reranker_type)
    return str(value or "")


def _rag_cache_hit(trace: dict[str, Any] | None) -> bool:
    config = _rag_config(trace)
    return bool(config.get("cache_hit") or _trace_attributes(trace).get("rag_cache_hit"))


def _extract_usage(response: dict[str, Any], trace: dict[str, Any] | None) -> dict[str, Any]:
    attrs = _trace_attributes(trace)
    prompt_tokens = int(attrs.get("prompt_tokens") or response.get("prompt_tokens") or 0)
    completion_tokens = int(attrs.get("completion_tokens") or response.get("completion_tokens") or 0)
    total_tokens = int(attrs.get("total_tokens") or response.get("total_tokens") or 0)
    estimated_cost = float(attrs.get("estimated_cost") or response.get("estimated_cost") or 0.0)
    usage_source = attrs.get("usage_source") or response.get("usage_source")
    if not usage_source:
        usage_source = "estimated" if total_tokens else "unavailable"
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost": round(estimated_cost, 6),
        "usage_source": str(usage_source),
    }


def _ratio(results: list[dict[str, Any]], key: str) -> float:
    if not results:
        return 0.0
    return round(sum(1 for item in results if item.get(key)) / len(results), 4)


def _conditional_ratio(
    results: list[dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
    value_key: str,
    empty_value: float = 1.0,
) -> float:
    scoped = [item for item in results if predicate(item)]
    if not scoped:
        return empty_value
    return round(sum(1 for item in scoped if item.get(value_key)) / len(scoped), 4)


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((percentile / 100) * len(ordered) + 0.5) - 1))
    return round(ordered[index], 2)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_safety_action(response: dict[str, Any]) -> str:
    safety = response.get("safety_result") or {}
    for key in ("input_safety", "output_safety", "tool_param_safety"):
        result = safety.get(key) if isinstance(safety, dict) else None
        if isinstance(result, dict) and result.get("action"):
            return str(result["action"])
    if response.get("error") in {"SAFETY_INPUT_BLOCKED", "SAFETY_OUTPUT_BLOCKED", "SAFETY_BLOCKED"}:
        return "block"
    return "allow"


def _matches_safety_action(expected: str, actual: str) -> bool:
    if expected == "allow":
        return actual == "allow"
    if expected == "block":
        return actual == "block"
    if expected == "review":
        return actual == "review"
    return expected == actual
