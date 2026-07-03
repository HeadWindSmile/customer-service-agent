from typing import Any

from app.observability.tracing import add_attribute, add_event, end_span, start_span


try:
    from langchain_core.callbacks import BaseCallbackHandler
except Exception:  # pragma: no cover - langchain-core 是项目依赖，这里只是保留降级边界。
    BaseCallbackHandler = object  # type: ignore


class TraceCallbackHandler(BaseCallbackHandler):
    """LangChain callback 占位实现。

    当前阶段先保留和 LCEL 对接的观测入口，避免把模型调用统计写死在业务代码里。
    后续如果真实 provider 返回 usage，可在这里把 token/cost 精确写入当前 trace。
    """

    def __init__(self) -> None:
        super().__init__()
        self._llm_span = None

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        self._llm_span = start_span("llm.callback", {"prompt_count": len(prompts)})
        add_event("llm.start", {"serialized_name": serialized.get("name") or serialized.get("id")})

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        usage = getattr(response, "llm_output", None) or {}
        token_usage = usage.get("token_usage") if isinstance(usage, dict) else None
        if token_usage:
            add_attribute("llm_usage", token_usage)
        add_event("llm.end", {"has_usage": bool(token_usage)})
        end_span(self._llm_span)
        self._llm_span = None

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        add_event("llm.error", {"error": str(error)})
        end_span(self._llm_span, error=str(error))
        self._llm_span = None
