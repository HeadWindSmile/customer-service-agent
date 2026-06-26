from dataclasses import dataclass, field
from time import perf_counter
from typing import Any
from uuid import uuid4


@dataclass
class TraceContext:
    """轻量 trace 上下文，后续可扩展为完整 span/callback 体系。"""

    trace_id: str
    started_at: float
    attributes: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(cls) -> "TraceContext":
        return cls(trace_id=uuid4().hex, started_at=perf_counter())

    @property
    def latency_ms(self) -> float:
        return round((perf_counter() - self.started_at) * 1000, 2)

    def add_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def to_log_payload(self) -> dict[str, Any]:
        return {"trace_id": self.trace_id, "latency_ms": self.latency_ms, **self.attributes}

