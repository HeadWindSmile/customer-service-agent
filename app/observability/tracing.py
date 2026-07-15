from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4


LATENCY_BREAKDOWN_STAGES = (
    "safety.input",
    "memory.load",
    "query.rewrite",
    "intent.classify",
    "auth.build_context",
    "router.route",
    "rag.retrieve",
    "rag.answer",
    "tool.call",
    "safety.output",
    "memory.save",
    "event.publish",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TraceEvent:
    """trace 内部事件。

    它和 app/events 里的业务事件不是一回事：这里记录链路上的时间点事实，
    例如“检索完成”“LLM fallback”；业务事件仍由 EventBus 负责建模和投递。
    """

    name: str
    timestamp: str
    attributes: dict[str, Any] = field(default_factory=dict)
    span_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp,
            "span_id": self.span_id,
            "attributes": self.attributes,
        }


@dataclass
class TraceSpan:
    """一次有明确耗时边界的链路阶段。

    当前 Demo 不接入完整 APM 平台，但 span 结构先保持清晰，后续接
    OpenTelemetry 或 LangChain callback 时可以把这些字段映射过去。
    """

    name: str
    span_id: str = field(default_factory=lambda: uuid4().hex[:16])
    parent_span_id: str | None = None
    started_at: str = field(default_factory=_utc_now)
    _started_perf: float = field(default_factory=perf_counter, repr=False)
    ended_at: str | None = None
    _ended_perf: float | None = field(default=None, repr=False)
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    error: str | None = None

    @property
    def latency_ms(self) -> float:
        ended = self._ended_perf or perf_counter()
        return round((ended - self._started_perf) * 1000, 2)

    def end(self, error: str | None = None) -> None:
        if self.ended_at is not None:
            return
        self.ended_at = _utc_now()
        self._ended_perf = perf_counter()
        if error:
            self.status = "error"
            self.error = error

    def add_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "error": self.error,
            "attributes": self.attributes,
        }


@dataclass
class TraceContext:
    """一次 /api/chat 请求的完整 trace 上下文。

    第十阶段仍保持本地文件存储和轻量结构，避免提前变成完整 APM 平台；
    但通过 trace_id、span、event、attribute 已经能支撑面试演示里的链路回放。
    """

    trace_id: str
    started_at: float
    created_at: str = field(default_factory=_utc_now)
    ended_at: str | None = None
    _ended_perf: float | None = field(default=None, repr=False)
    attributes: dict[str, Any] = field(default_factory=dict)
    spans: list[TraceSpan] = field(default_factory=list)
    events: list[TraceEvent] = field(default_factory=list)
    _active_span_ids: list[str] = field(default_factory=list, repr=False)

    @classmethod
    def new(cls) -> "TraceContext":
        return cls(trace_id=uuid4().hex, started_at=perf_counter())

    @property
    def latency_ms(self) -> float:
        ended = self._ended_perf or perf_counter()
        return round((ended - self.started_at) * 1000, 2)

    def add_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> TraceSpan:
        parent_span_id = self._active_span_ids[-1] if self._active_span_ids else None
        span = TraceSpan(name=name, parent_span_id=parent_span_id, attributes=attributes or {})
        self.spans.append(span)
        self._active_span_ids.append(span.span_id)
        return span

    def end_span(self, span: TraceSpan | str | None = None, error: str | None = None) -> None:
        if span is None:
            span_id = self._active_span_ids[-1] if self._active_span_ids else None
        elif isinstance(span, TraceSpan):
            span_id = span.span_id
        else:
            span_id = span
        if span_id is None:
            return

        matched = next((item for item in self.spans if item.span_id == span_id), None)
        if matched:
            matched.end(error=error)
        if span_id in self._active_span_ids:
            self._active_span_ids.remove(span_id)

    def add_event(self, name: str, attributes: dict[str, Any] | None = None, span_id: str | None = None) -> None:
        current_span_id = span_id or (self._active_span_ids[-1] if self._active_span_ids else None)
        self.events.append(
            TraceEvent(
                name=name,
                timestamp=_utc_now(),
                span_id=current_span_id,
                attributes=attributes or {},
            )
        )

    def finish(self, error: str | None = None) -> None:
        while self._active_span_ids:
            self.end_span(error=error)
        if self.ended_at is None:
            self.ended_at = _utc_now()
            self._ended_perf = perf_counter()
        if error:
            self.add_attribute("error", error)
        self.add_attribute("latency_breakdown", self.latency_breakdown())

    def latency_breakdown(self) -> dict[str, Any]:
        """把 span 汇总成适合单次请求演示的耗时拆解。

        span 仍保留完整明细；breakdown 是面试演示和排查时更易读的摘要。Router
        span 包含其子阶段耗时，因此这里明确标注为 inclusive，避免把所有阶段简单
        相加后误解为总耗时。
        """

        stages: dict[str, dict[str, Any]] = {}
        for stage in LATENCY_BREAKDOWN_STAGES:
            matched = [span for span in self.spans if span.name == stage]
            if not matched:
                stages[stage] = {
                    "count": 0,
                    "latency_ms": 0.0,
                    "avg_latency_ms": 0.0,
                    "status": "not_run",
                }
                continue
            latency_ms = round(sum(span.latency_ms for span in matched), 2)
            status = "error" if any(span.status == "error" for span in matched) else "ok"
            payload: dict[str, Any] = {
                "count": len(matched),
                "latency_ms": latency_ms,
                "avg_latency_ms": round(latency_ms / len(matched), 2),
                "status": status,
            }
            if stage == "router.route":
                payload["inclusive"] = True
            stages[stage] = payload

        tracked_names = set(LATENCY_BREAKDOWN_STAGES)
        untracked_latency_ms = round(sum(span.latency_ms for span in self.spans if span.name not in tracked_names), 2)
        return {
            "total_latency_ms": self.latency_ms,
            "stages": stages,
            "untracked_latency_ms": untracked_latency_ms,
            "note": "router.route 是包含子阶段的耗时；rag/tool/event 等子阶段已单独列出。",
        }

    def to_log_payload(self) -> dict[str, Any]:
        return {"trace_id": self.trace_id, "latency_ms": self.latency_ms, **self.attributes}

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "ended_at": self.ended_at,
            "latency_ms": self.latency_ms,
            "attributes": self.attributes,
            "spans": [span.to_dict() for span in self.spans],
            "events": [event.to_dict() for event in self.events],
        }


@dataclass(frozen=True)
class TraceContextToken:
    """ContextVar reset 所需 token，防止异步请求之间串 trace。"""

    context_token: Token[TraceContext | None]
    trace_id_token: Token[str]


_current_trace_context: ContextVar[TraceContext | None] = ContextVar("current_trace_context", default=None)
_current_trace_id: ContextVar[str] = ContextVar("current_trace_id", default="")


def set_current_trace(trace: TraceContext) -> TraceContextToken:
    return TraceContextToken(
        context_token=_current_trace_context.set(trace),
        trace_id_token=_current_trace_id.set(trace.trace_id),
    )


def reset_current_trace(token: TraceContextToken) -> None:
    _current_trace_context.reset(token.context_token)
    _current_trace_id.reset(token.trace_id_token)


def get_current_trace() -> TraceContext | None:
    return _current_trace_context.get()


def get_current_trace_id() -> str:
    return _current_trace_id.get()


def add_attribute(key: str, value: Any) -> None:
    trace = get_current_trace()
    if trace:
        trace.add_attribute(key, value)


def add_event(name: str, attributes: dict[str, Any] | None = None) -> None:
    trace = get_current_trace()
    if trace:
        trace.add_event(name, attributes)


def start_span(name: str, attributes: dict[str, Any] | None = None) -> TraceSpan | None:
    trace = get_current_trace()
    if trace is None:
        return None
    return trace.start_span(name, attributes)


def end_span(span: TraceSpan | str | None = None, error: str | None = None) -> None:
    trace = get_current_trace()
    if trace:
        trace.end_span(span, error=error)
