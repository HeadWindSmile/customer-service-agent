from app.observability.tracing import add_event, get_current_trace


def estimate_tokens(text: str) -> int:
    """本地 token 粗估。

    当前 Demo 默认使用 MockLLM，拿不到真实 provider usage；这里用字符数近似，
    只用于第十阶段评测和 trace 演示，不代表生产计费口径。
    """

    normalized = " ".join(str(text).split())
    if not normalized:
        return 0
    return max(1, round(len(normalized) / 2))


def record_llm_usage(
    *,
    provider: str,
    model_name: str,
    prompt_text: str,
    completion_text: str,
    stage: str,
    fallback_used: bool = False,
) -> dict[str, object]:
    prompt_tokens = estimate_tokens(prompt_text)
    completion_tokens = estimate_tokens(completion_text)
    total_tokens = prompt_tokens + completion_tokens
    estimated_cost = estimate_cost(provider, prompt_tokens, completion_tokens)
    usage = {
        "stage": stage,
        "provider": provider,
        "model_name": model_name,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost": estimated_cost,
        "usage_source": "estimated",
        "fallback_used": fallback_used,
    }

    trace = get_current_trace()
    if trace is not None:
        calls = list(trace.attributes.get("llm_calls") or [])
        calls.append(usage)
        trace.add_attribute("llm_calls", calls)
        trace.add_attribute("llm_provider", provider)
        trace.add_attribute("model_name", model_name)
        trace.add_attribute("prompt_tokens", int(trace.attributes.get("prompt_tokens") or 0) + prompt_tokens)
        trace.add_attribute("completion_tokens", int(trace.attributes.get("completion_tokens") or 0) + completion_tokens)
        trace.add_attribute("total_tokens", int(trace.attributes.get("total_tokens") or 0) + total_tokens)
        trace.add_attribute(
            "estimated_cost",
            round(float(trace.attributes.get("estimated_cost") or 0.0) + estimated_cost, 6),
        )
        trace.add_attribute("usage_source", "estimated")
    add_event("llm.usage_recorded", usage)
    return usage


def estimate_cost(provider: str, prompt_tokens: int, completion_tokens: int) -> float:
    """估算成本。

    mock 模式成本为 0；其他 provider 只给演示用粗估，后续接真实模型时应以
    response.usage 或供应商账单字段为准。
    """

    if provider == "mock":
        return 0.0
    return round((prompt_tokens + completion_tokens) * 0.000002, 6)
