from collections import defaultdict, deque
from threading import Lock
from time import perf_counter
from typing import Any

from app.config import settings


class MetricsLiteRecorder:
    """进程内轻量指标。

    第 11 阶段只需要本地部署演示的基础观测信号，因此这里刻意不用 Prometheus
    client 或外部指标系统，避免把 Demo 提前扩展成生产级监控平台。
    """

    def __init__(self, window_size: int | None = None) -> None:
        self.window_size = max(1, window_size or settings.metrics_lite_window_size)
        self.started_at = perf_counter()
        self._lock = Lock()
        self._latencies: deque[float] = deque(maxlen=self.window_size)
        self._total_requests = 0
        self._success_requests = 0
        self._error_requests = 0
        self._in_flight = 0
        self._by_path: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "success": 0, "error": 0, "latency_ms": deque(maxlen=self.window_size)}
        )

    def start_request(self) -> None:
        with self._lock:
            self._in_flight += 1

    def record_request(self, method: str, path: str, status_code: int, latency_ms: float) -> None:
        route_key = f"{method.upper()} {path}"
        success = status_code < 500
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
            self._total_requests += 1
            if success:
                self._success_requests += 1
            else:
                self._error_requests += 1
            self._latencies.append(latency_ms)
            route = self._by_path[route_key]
            route["count"] += 1
            route["success"] += 1 if success else 0
            route["error"] += 0 if success else 1
            route["latency_ms"].append(latency_ms)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            latencies = list(self._latencies)
            by_path = {
                key: {
                    "count": value["count"],
                    "success": value["success"],
                    "error": value["error"],
                    "avg_latency_ms": _avg(list(value["latency_ms"])),
                    "p95_latency_ms": _percentile(list(value["latency_ms"]), 95),
                }
                for key, value in sorted(self._by_path.items())
            }
            uptime_seconds = round(perf_counter() - self.started_at, 2)
            return {
                "enabled": settings.metrics_lite_enabled,
                "scope": "single_process",
                "note": "轻量本地指标，仅用于 Demo 验收，不代表生产级监控或容量结论。",
                "uptime_seconds": uptime_seconds,
                "window_size": self.window_size,
                "in_flight_requests": self._in_flight,
                "total_requests": self._total_requests,
                "success_requests": self._success_requests,
                "error_requests": self._error_requests,
                "success_rate": _ratio(self._success_requests, self._total_requests),
                "avg_latency_ms": _avg(latencies),
                "p95_latency_ms": _percentile(latencies, 95),
                "paths": by_path,
            }


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


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(part / total, 4)


metrics_recorder = MetricsLiteRecorder()
