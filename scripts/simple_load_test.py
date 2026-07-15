import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx


DISCLAIMER = "本报告只代表本机小流量 Demo 验证，不代表生产容量承诺或线上 SLA。"


SCENARIOS: dict[str, list[dict[str, Any]]] = {
    "faq": [
        {
            "user_id": "u1001",
            "session_id": "load-faq",
            "role": "user",
            "message": "套餐变更什么时候生效？",
        }
    ],
    "package": [
        {
            "user_id": "u1001",
            "session_id": "load-package",
            "role": "user",
            "message": "查询我的当前套餐",
        }
    ],
    "package_query": [
        {
            "user_id": "u1001",
            "session_id": "load-package",
            "role": "user",
            "message": "查询我的当前套餐",
        }
    ],
    "bill_query": [
        {
            "user_id": "u1001",
            "session_id": "load-bill",
            "role": "user",
            "message": "帮我查本月账单",
        }
    ],
    "fault_diagnosis": [
        {
            "user_id": "u1001",
            "session_id": "load-fault",
            "role": "user",
            "message": "宽带连不上应该怎么排查？",
        }
    ],
    "offer": [
        {
            "user_id": "u1001",
            "session_id": "load-offer",
            "role": "user",
            "message": "我流量不够，预算20元以内，推荐一个优惠",
        }
    ],
    "order": [
        {
            "user_id": "agent001",
            "session_id": "load-order",
            "role": "agent",
            "target_user_id": "u1001",
            "message": "帮客户查订单 ORD-20260701001 的状态",
        }
    ],
}

SCENARIOS["mixed"] = [
    SCENARIOS["faq"][0],
    SCENARIOS["package"][0],
    SCENARIOS["bill_query"][0],
    SCENARIOS["fault_diagnosis"][0],
    SCENARIOS["offer"][0],
    SCENARIOS["order"][0],
]


async def run_load_test(
    *,
    base_url: str,
    scenario: str,
    concurrency: int,
    total_requests: int,
    timeout: float,
) -> dict[str, Any]:
    """小规模并发调用脚本。

    该脚本服务于第 17 阶段性能报告演示，只生成本地小流量统计，不做生产容量
    结论；真实压测还需要隔离环境、稳定数据集、监控平台和更长时间窗口。
    """

    if scenario not in SCENARIOS:
        raise ValueError(f"未知 scenario：{scenario}，可选值：{', '.join(sorted(SCENARIOS))}")
    concurrency = max(1, concurrency)
    total_requests = max(1, total_requests)
    semaphore = asyncio.Semaphore(concurrency)
    payload_templates = SCENARIOS[scenario]
    started = perf_counter()
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout) as client:
        tasks = [
            _send_one(client, semaphore, payload_templates[index % len(payload_templates)], index)
            for index in range(total_requests)
        ]
        results = await asyncio.gather(*tasks)

    latencies = [item["latency_ms"] for item in results if item["ok"]]
    failed = [item for item in results if not item["ok"]]
    duration_seconds = round(perf_counter() - started, 2)
    by_intent = Counter(str(item.get("intent") or "unknown") for item in results)
    by_status_code = Counter(str(item.get("status_code") or "exception") for item in results)
    by_error = Counter(str(item.get("error") or "none") for item in results if not item["ok"])
    return {
        "scenario": scenario,
        "base_url": base_url.rstrip("/"),
        "concurrency": concurrency,
        "total_requests": total_requests,
        "success_requests": len(latencies),
        "failed_requests": len(failed),
        "success_rate": _ratio(len(latencies), total_requests),
        "error_rate": _ratio(len(failed), total_requests),
        "avg_latency_ms": _avg(latencies),
        "p50_latency_ms": _percentile(latencies, 50),
        "p95_latency_ms": _percentile(latencies, 95),
        "max_latency_ms": round(max(latencies), 2) if latencies else 0.0,
        "duration_seconds": duration_seconds,
        "throughput_rps": round(total_requests / duration_seconds, 2) if duration_seconds > 0 else 0.0,
        "by_intent": dict(sorted(by_intent.items())),
        "by_status_code": dict(sorted(by_status_code.items())),
        "by_error": dict(sorted(by_error.items())),
        "errors": failed[:5],
        "disclaimer": DISCLAIMER,
    }


async def _send_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    payload_template: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    payload = dict(payload_template)
    payload["session_id"] = f"{payload_template['session_id']}-{index}"
    async with semaphore:
        started = perf_counter()
        try:
            response = await client.post("/api/chat", json=payload)
            latency_ms = round((perf_counter() - started) * 1000, 2)
            data = response.json()
            return {
                "ok": response.status_code == 200 and not data.get("error"),
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "intent": data.get("intent"),
                "trace_id": data.get("trace_id"),
                "error": data.get("error"),
            }
        except Exception as exc:
            latency_ms = round((perf_counter() - started) * 1000, 2)
            return {"ok": False, "latency_ms": latency_ms, "error": str(exc)}


def write_reports(result: dict[str, Any], json_report: str, markdown_report: str | None = None) -> tuple[Path, Path]:
    json_path = Path(json_report)
    md_path = Path(markdown_report) if markdown_report else json_path.with_suffix(".md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown_report(result), encoding="utf-8")
    return json_path, md_path


def build_markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# 本地性能验证报告",
        "",
        f"> {result.get('disclaimer') or DISCLAIMER}",
        "",
        "## 基本信息",
        "",
        f"- base_url: `{result['base_url']}`",
        f"- scenario: `{result['scenario']}`",
        f"- concurrency: `{result['concurrency']}`",
        f"- total_requests: `{result['total_requests']}`",
        f"- duration_seconds: `{result['duration_seconds']}`",
        f"- throughput_rps: `{result['throughput_rps']}`",
        "",
        "## 核心指标",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| success_rate | {result['success_rate']} |",
        f"| error_rate | {result['error_rate']} |",
        f"| avg_latency_ms | {result['avg_latency_ms']} |",
        f"| p50_latency_ms | {result['p50_latency_ms']} |",
        f"| p95_latency_ms | {result['p95_latency_ms']} |",
        f"| max_latency_ms | {result['max_latency_ms']} |",
        "",
        "## intent 分布",
        "",
        "| intent | count |",
        "|---|---:|",
    ]
    for intent, count in (result.get("by_intent") or {}).items():
        lines.append(f"| {intent} | {count} |")
    lines.extend(["", "## status_code 分布", "", "| status_code | count |", "|---|---:|"])
    for status_code, count in (result.get("by_status_code") or {}).items():
        lines.append(f"| {status_code} | {count} |")
    if result.get("by_error"):
        lines.extend(["", "## 错误分布", "", "| error | count |", "|---|---:|"])
        for error, count in result["by_error"].items():
            lines.append(f"| {error} | {count} |")
    lines.extend(
        [
            "",
            "## 边界说明",
            "",
            "本脚本运行在本地 Demo 环境，通常使用 mock/fallback 依赖，只适合验证链路和报告口径。",
            "生产容量评估需要独立压测环境、稳定业务数据、真实依赖、持续监控和更长时间窗口。",
            "",
        ]
    )
    return "\n".join(lines)


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


def main() -> None:
    parser = argparse.ArgumentParser(description="运行本地小规模并发验证。")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="AI 服务地址。")
    parser.add_argument("--scenario", default="faq", choices=sorted(SCENARIOS), help="请求场景。")
    parser.add_argument("--concurrency", type=int, default=5, help="并发数，建议保持较小。")
    parser.add_argument("--total-requests", type=int, default=20, help="总请求数。")
    parser.add_argument("--timeout", type=float, default=15.0, help="单次请求超时时间。")
    parser.add_argument("--report", default="reports/load_test_report.json", help="JSON 报告输出路径。")
    parser.add_argument("--markdown-report", default="", help="Markdown 报告输出路径，默认和 JSON 同名。")
    args = parser.parse_args()
    result = asyncio.run(
        run_load_test(
            base_url=args.base_url,
            scenario=args.scenario,
            concurrency=args.concurrency,
            total_requests=args.total_requests,
            timeout=args.timeout,
        )
    )
    json_path, md_path = write_reports(
        result,
        json_report=args.report,
        markdown_report=args.markdown_report or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"JSON 报告已写入：{json_path}")
    print(f"Markdown 报告已写入：{md_path}")


if __name__ == "__main__":
    main()
