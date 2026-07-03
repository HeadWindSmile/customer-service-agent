import argparse
import json
import sys
from typing import Any

import httpx


def run_smoke_test(base_url: str, timeout: float) -> dict[str, Any]:
    """最小部署冒烟测试。

    这里只验证服务是否可用和两条核心链路是否跑通，不替代 pytest，也不做性能结论。
    """

    base_url = base_url.rstrip("/")
    results: list[dict[str, Any]] = []
    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        results.append(_check_get(client, "/health"))
        results.append(_check_get(client, "/ready"))
        results.append(
            _check_chat(
                client,
                "faq",
                {
                    "user_id": "u1001",
                    "session_id": "smoke-faq",
                    "role": "user",
                    "message": "套餐变更什么时候生效？",
                },
                expected_intent="faq_query",
            )
        )
        results.append(
            _check_chat(
                client,
                "package_query",
                {
                    "user_id": "u1001",
                    "session_id": "smoke-package",
                    "role": "user",
                    "message": "查询我的当前套餐",
                },
                expected_intent="package_query",
            )
        )

    passed = all(item["ok"] for item in results)
    return {
        "passed": passed,
        "base_url": base_url,
        "checks": results,
        "note": "smoke test 只验证本地部署核心链路，不代表生产稳定性。",
    }


def _check_get(client: httpx.Client, path: str) -> dict[str, Any]:
    try:
        response = client.get(path)
        return {
            "name": f"GET {path}",
            "ok": response.status_code < 400,
            "status_code": response.status_code,
            "body": response.json(),
        }
    except Exception as exc:
        return {"name": f"GET {path}", "ok": False, "error": str(exc)}


def _check_chat(
    client: httpx.Client,
    name: str,
    payload: dict[str, Any],
    *,
    expected_intent: str,
) -> dict[str, Any]:
    try:
        response = client.post("/api/chat", json=payload)
        data = response.json()
        ok = response.status_code == 200 and data.get("intent") == expected_intent and not data.get("error")
        return {
            "name": f"POST /api/chat {name}",
            "ok": ok,
            "status_code": response.status_code,
            "intent": data.get("intent"),
            "trace_id": data.get("trace_id"),
            "latency_ms": data.get("latency_ms"),
            "error": data.get("error"),
        }
    except Exception as exc:
        return {"name": f"POST /api/chat {name}", "ok": False, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="运行本地部署冒烟测试。")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="AI 服务地址。")
    parser.add_argument("--timeout", type=float, default=10.0, help="单次请求超时时间。")
    args = parser.parse_args()
    result = run_smoke_test(args.base_url, args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
