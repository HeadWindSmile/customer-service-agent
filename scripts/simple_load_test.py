import argparse
import asyncio
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx


SCENARIOS: dict[str, dict[str, Any]] = {
    "faq": {
        "user_id": "u1001",
        "session_id": "load-faq",
        "role": "user",
        "message": "套餐变更什么时候生效？",
    },
    "bill_query": {
        "user_id": "u1001",
        "session_id": "load-bill",
        "role": "user",
        "message": "帮我查本月账单",
    },
    "package_query": {
        "user_id": "u1001",
        "session_id": "load-package",
        "role": "user",
        "message": "查询我的当前套餐",
    },
    "fault_diagnosis": {
        "user_id": "u1001",
        "session_id": "load-fault",
        "role": "user",
        "message": "宽带连不上应该怎么排查？",
    },
}


async def run_load_test(
    *,
    base_url: str,
    scenario: str,
    concurrency: int,
    total_requests: int,
    timeout: float,
) -> dict[str, Any]:
    """小规模并发调用脚本。

    该脚本用于第 11 阶段部署验收，只输出基础延迟统计，不作为容量评估或生产压测。
    """

    if scenario not in SCENARIOS:
        raise ValueError(f"未知 scenario：{scenario}，可选值：{', '.join(sorted(SCENARIOS))}")
    concurrency = max(1, concurrency)
    total_requests = max(1, total_requests)
    semaphore = asyncio.Semaphore(concurrency)
    payload_template = SCENARIOS[scenario]
    started = perf_counter()
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout) as client:
        tasks = [
            _send_one(client, semaphore, payload_template, index)
            for index in range(total_requests)
        ]
        results = await asyncio.gather(*tasks)

    latencies = [item["latency_ms"] for item in results if item["ok"]]
    failed = [item for item in results if not item["ok"]]
    return {
        "scenario": scenario,
        "base_url": base_url.rstrip("/"),
        "concurrency": concurrency,
        "total_requests": total_requests,
        "success_requests": len(latencies),
        "failed_requests": len(failed),
        "success_rate": _ratio(len(latencies), total_requests),
        "avg_latency_ms": _avg(latencies),
        "p95_latency_ms": _percentile(latencies, 95),
        "p99_latency_ms": _percentile(latencies, 99),
        "duration_seconds": round(perf_counter() - started, 2),
        "errors": failed[:5],
        "note": "本脚本只做本地小流量验证，不代表生产级高并发能力。",
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
                "error": data.get("error"),
            }
        except Exception as exc:
            latency_ms = round((perf_counter() - started) * 1000, 2)
            return {"ok": False, "latency_ms": latency_ms, "error": str(exc)}


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
    parser.add_argument("--report", default="reports/load_test_report.json", help="报告输出路径。")
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
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"报告已写入：{report_path}")


if __name__ == "__main__":
    main()
