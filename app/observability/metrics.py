from collections import defaultdict, deque
from math import inf
from threading import Lock
from time import perf_counter
from typing import Any

from app.config import settings


DEFAULT_LATENCY_BUCKETS_SECONDS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    inf,
)


METRIC_PREFIX = "customer_service_agent_"


METRIC_METADATA: dict[str, tuple[str, str]] = {
    "customer_service_agent_http_requests_total": ("counter", "Total HTTP requests handled by this process."),
    "customer_service_agent_http_errors_total": ("counter", "Total HTTP 5xx responses handled by this process."),
    "customer_service_agent_http_request_latency_seconds": ("histogram", "HTTP request latency in seconds."),
    "customer_service_agent_http_in_flight_requests": ("gauge", "Current in-flight HTTP requests."),
    "customer_service_agent_chat_requests_total": ("counter", "Total chat requests by intent and result."),
    "customer_service_agent_chat_errors_total": ("counter", "Total chat errors by intent and error type."),
    "customer_service_agent_chat_latency_seconds": ("histogram", "End-to-end chat request latency in seconds."),
    "customer_service_agent_intent_classifications_total": ("counter", "Intent classification results."),
    "customer_service_agent_trace_stage_latency_seconds": ("histogram", "Trace stage latency in seconds."),
    "customer_service_agent_safety_checks_total": ("counter", "Safety checks by scope, action and risk level."),
    "customer_service_agent_safety_review_queued_total": ("counter", "Safety review queue events."),
    "customer_service_agent_tool_calls_total": ("counter", "Tool calls by tool name and result."),
    "customer_service_agent_tool_call_latency_seconds": ("histogram", "Tool call latency in seconds."),
    "customer_service_agent_business_client_requests_total": ("counter", "Business client calls by operation and result."),
    "customer_service_agent_business_client_request_latency_seconds": (
        "histogram",
        "Business client request latency in seconds.",
    ),
    "customer_service_agent_business_client_retries_total": ("counter", "Business client retry attempts."),
    "customer_service_agent_business_client_timeouts_total": ("counter", "Business client timeout errors."),
    "customer_service_agent_business_client_circuit_open_total": (
        "counter",
        "Business client circuit-open rejections.",
    ),
    "customer_service_agent_rag_retrievals_total": ("counter", "RAG retrievals by scenario and cache result."),
    "customer_service_agent_rag_sources_count": ("gauge", "Last observed number of returned RAG sources."),
    "customer_service_agent_cache_events_total": ("counter", "Cache events by cache name and result."),
    "customer_service_agent_cache_size": ("gauge", "Last observed cache size by cache name."),
    "customer_service_agent_events_published_total": ("counter", "Published events by event type and result."),
    "customer_service_agent_event_publish_latency_seconds": ("histogram", "Event publish latency in seconds."),
}


LabelKey = tuple[tuple[str, str], ...]


class MetricsLiteRecorder:
    """进程内指标记录器。

    第 17 阶段需要 Prometheus-compatible 文本接口，但仍不默认依赖 Prometheus
    server、Grafana 或 OTel Collector。这里用轻量内存聚合器统一支撑
    `/metrics-lite` JSON 和 `/metrics` 文本格式；真实生产环境后续可以把这些
    指标名和标签迁移到正式监控 SDK。
    """

    def __init__(
        self,
        window_size: int | None = None,
        buckets_seconds: tuple[float, ...] = DEFAULT_LATENCY_BUCKETS_SECONDS,
    ) -> None:
        self.window_size = max(1, window_size or settings.metrics_lite_window_size)
        self.buckets_seconds = buckets_seconds
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
        self._counters: dict[str, dict[LabelKey, float]] = defaultdict(lambda: defaultdict(float))
        self._gauges: dict[str, dict[LabelKey, float]] = defaultdict(dict)
        self._histograms: dict[str, dict[LabelKey, dict[str, Any]]] = defaultdict(dict)

    def start_request(self) -> None:
        with self._lock:
            self._in_flight += 1
            self._set_gauge_unlocked(
                "customer_service_agent_http_in_flight_requests",
                {},
                self._in_flight,
            )

    def record_request(self, method: str, path: str, status_code: int, latency_ms: float) -> None:
        normalized_path = _normalize_path(path)
        route_key = f"{method.upper()} {normalized_path}"
        success = status_code < 500
        labels = {"method": method.upper(), "path": normalized_path, "status": str(status_code)}
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

            self._inc_unlocked("customer_service_agent_http_requests_total", labels)
            if not success:
                self._inc_unlocked("customer_service_agent_http_errors_total", labels)
            self._observe_unlocked(
                "customer_service_agent_http_request_latency_seconds",
                {"method": method.upper(), "path": normalized_path},
                latency_ms / 1000,
            )
            self._set_gauge_unlocked(
                "customer_service_agent_http_in_flight_requests",
                {},
                self._in_flight,
            )

    def record_chat_request(
        self,
        *,
        intent: str,
        latency_ms: float,
        error_type: str | None = None,
    ) -> None:
        result = "error" if error_type else "success"
        labels = {"intent": _safe_label_value(intent or "unknown"), "result": result}
        with self._lock:
            self._inc_unlocked("customer_service_agent_chat_requests_total", labels)
            if error_type:
                self._inc_unlocked(
                    "customer_service_agent_chat_errors_total",
                    {"intent": _safe_label_value(intent or "unknown"), "error_type": _safe_label_value(error_type)},
                )
            self._observe_unlocked("customer_service_agent_chat_latency_seconds", labels, latency_ms / 1000)

    def record_intent_classification(self, *, intent: str, result: str = "classified") -> None:
        with self._lock:
            self._inc_unlocked(
                "customer_service_agent_intent_classifications_total",
                {"intent": _safe_label_value(intent or "unknown"), "result": _safe_label_value(result)},
            )

    def record_trace_stage_latency(self, *, stage: str, status: str, latency_ms: float) -> None:
        with self._lock:
            self._observe_unlocked(
                "customer_service_agent_trace_stage_latency_seconds",
                {"stage": _safe_label_value(stage), "status": _safe_label_value(status)},
                latency_ms / 1000,
            )

    def record_safety_check(
        self,
        *,
        scope: str,
        action: str,
        risk_level: str,
        review_queued: bool = False,
    ) -> None:
        labels = {
            "scope": _safe_label_value(scope),
            "action": _safe_label_value(action),
            "risk_level": _safe_label_value(risk_level),
        }
        with self._lock:
            self._inc_unlocked("customer_service_agent_safety_checks_total", labels)
            if review_queued:
                self._inc_unlocked(
                    "customer_service_agent_safety_review_queued_total",
                    {"scope": labels["scope"], "risk_level": labels["risk_level"]},
                )

    def record_tool_call(self, *, tool_name: str, success: bool, latency_ms: float) -> None:
        labels = {"tool_name": _safe_label_value(tool_name), "success": str(bool(success)).lower()}
        with self._lock:
            self._inc_unlocked("customer_service_agent_tool_calls_total", labels)
            self._observe_unlocked("customer_service_agent_tool_call_latency_seconds", labels, latency_ms / 1000)

    def record_business_client_request(
        self,
        *,
        operation: str,
        client_type: str,
        result: str,
        latency_ms: float,
        error_code: str = "",
        status_code: int | str | None = None,
    ) -> None:
        labels = {
            "operation": _safe_label_value(operation),
            "client_type": _safe_label_value(client_type),
            "result": _safe_label_value(result),
            "error_code": _safe_label_value(error_code or "none"),
            "status_code": str(status_code or "none"),
        }
        with self._lock:
            self._inc_unlocked("customer_service_agent_business_client_requests_total", labels)
            self._observe_unlocked(
                "customer_service_agent_business_client_request_latency_seconds",
                {
                    "operation": labels["operation"],
                    "client_type": labels["client_type"],
                    "result": labels["result"],
                },
                latency_ms / 1000,
            )

    def record_business_client_retry(self, *, operation: str, client_type: str) -> None:
        with self._lock:
            self._inc_unlocked(
                "customer_service_agent_business_client_retries_total",
                {"operation": _safe_label_value(operation), "client_type": _safe_label_value(client_type)},
            )

    def record_business_client_timeout(self, *, operation: str, client_type: str) -> None:
        with self._lock:
            self._inc_unlocked(
                "customer_service_agent_business_client_timeouts_total",
                {"operation": _safe_label_value(operation), "client_type": _safe_label_value(client_type)},
            )

    def record_business_client_circuit_open(self, *, operation: str, client_type: str) -> None:
        with self._lock:
            self._inc_unlocked(
                "customer_service_agent_business_client_circuit_open_total",
                {"operation": _safe_label_value(operation), "client_type": _safe_label_value(client_type)},
            )

    def record_rag_retrieval(self, *, scenario: str, cache_hit: bool, source_count: int) -> None:
        labels = {"scenario": _safe_label_value(scenario), "cache_hit": str(bool(cache_hit)).lower()}
        with self._lock:
            self._inc_unlocked("customer_service_agent_rag_retrievals_total", labels)
            self._set_gauge_unlocked(
                "customer_service_agent_rag_sources_count",
                {"scenario": labels["scenario"]},
                source_count,
            )

    def record_cache_event(self, *, cache_name: str, result: str, size: int | None = None) -> None:
        labels = {"cache_name": _safe_label_value(cache_name), "result": _safe_label_value(result)}
        with self._lock:
            self._inc_unlocked("customer_service_agent_cache_events_total", labels)
            if size is not None:
                self._set_gauge_unlocked(
                    "customer_service_agent_cache_size",
                    {"cache_name": labels["cache_name"]},
                    size,
                )

    def record_event_publish(
        self,
        *,
        event_type: str,
        producer_type: str,
        success: bool,
        latency_ms: float,
    ) -> None:
        labels = {
            "event_type": _safe_label_value(event_type),
            "producer_type": _safe_label_value(producer_type),
            "result": "success" if success else "failure",
        }
        with self._lock:
            self._inc_unlocked("customer_service_agent_events_published_total", labels)
            self._observe_unlocked("customer_service_agent_event_publish_latency_seconds", labels, latency_ms / 1000)

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

    def prometheus_text(self) -> str:
        """导出 Prometheus 0.0.4 文本格式。

        这里只做单进程内存导出；多 worker 聚合、长期存储和告警规则留给后续真实
        Prometheus/Grafana/OTel 接入阶段。
        """

        with self._lock:
            lines: list[str] = []
            metric_names = sorted(
                set(self._counters)
                | set(self._gauges)
                | set(self._histograms)
                | {"customer_service_agent_http_in_flight_requests"}
            )
            for name in metric_names:
                metric_type, help_text = METRIC_METADATA.get(name, ("gauge", "Customer service agent metric."))
                lines.append(f"# HELP {name} {_escape_help(help_text)}")
                lines.append(f"# TYPE {name} {metric_type}")
                if metric_type == "counter":
                    for labels, value in sorted(self._counters.get(name, {}).items()):
                        lines.append(f"{name}{_format_labels(labels)} {_format_number(value)}")
                elif metric_type == "histogram":
                    for labels, payload in sorted(self._histograms.get(name, {}).items()):
                        for bucket in self.buckets_seconds:
                            bucket_labels = tuple(list(labels) + [("le", _bucket_label(bucket))])
                            lines.append(
                                f"{name}_bucket{_format_labels(bucket_labels)} "
                                f"{_format_number(payload['buckets'].get(bucket, 0))}"
                            )
                        lines.append(f"{name}_sum{_format_labels(labels)} {_format_number(payload['sum'])}")
                        lines.append(f"{name}_count{_format_labels(labels)} {_format_number(payload['count'])}")
                else:
                    gauge_values = self._gauges.get(name, {})
                    if name == "customer_service_agent_http_in_flight_requests" and not gauge_values:
                        gauge_values = {_labels_key({}): float(self._in_flight)}
                    for labels, value in sorted(gauge_values.items()):
                        lines.append(f"{name}{_format_labels(labels)} {_format_number(value)}")
            lines.append("")
            return "\n".join(lines)

    def reset(self) -> None:
        """测试辅助：重置当前 recorder 状态，生产代码不调用。"""

        with self._lock:
            self.started_at = perf_counter()
            self._latencies.clear()
            self._total_requests = 0
            self._success_requests = 0
            self._error_requests = 0
            self._in_flight = 0
            self._by_path.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()

    def _inc_unlocked(self, name: str, labels: dict[str, str], amount: float = 1.0) -> None:
        self._counters[name][_labels_key(labels)] += amount

    def _set_gauge_unlocked(self, name: str, labels: dict[str, str], value: float) -> None:
        self._gauges[name][_labels_key(labels)] = float(value)

    def _observe_unlocked(self, name: str, labels: dict[str, str], value: float) -> None:
        key = _labels_key(labels)
        payload = self._histograms[name].setdefault(
            key,
            {
                "buckets": {bucket: 0.0 for bucket in self.buckets_seconds},
                "sum": 0.0,
                "count": 0.0,
            },
        )
        for bucket in self.buckets_seconds:
            if value <= bucket:
                payload["buckets"][bucket] += 1
        payload["sum"] += value
        payload["count"] += 1


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


def _normalize_path(path: str) -> str:
    if path.startswith("/api/traces/"):
        return "/api/traces/{trace_id}"
    return path


def _labels_key(labels: dict[str, str]) -> LabelKey:
    return tuple(sorted((key, _safe_label_value(value)) for key, value in labels.items()))


def _format_labels(labels: LabelKey) -> str:
    if not labels:
        return ""
    body = ",".join(f'{key}="{_escape_label(value)}"' for key, value in labels)
    return "{" + body + "}"


def _escape_label(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _escape_help(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n")


def _safe_label_value(value: object) -> str:
    text = str(value or "unknown").strip()
    if not text:
        return "unknown"
    # labels 只保留低基数字段；这里限制长度，避免错误消息或业务 ID 意外进入指标。
    return text[:80]


def _bucket_label(bucket: float) -> str:
    if bucket == inf:
        return "+Inf"
    return f"{bucket:g}"


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


metrics_recorder = MetricsLiteRecorder()
