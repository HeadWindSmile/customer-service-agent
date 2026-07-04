#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

# 演示前检查只验证核心链路，不替代 pytest 或离线评测。
python scripts/smoke_test.py --base-url "$BASE_URL"

python - "$BASE_URL" <<'PY'
import json
import sys

import httpx

base_url = sys.argv[1].rstrip("/")
cases = [
    ("套餐规则", {"user_id": "u1001", "session_id": "demo-check-faq", "role": "user", "message": "套餐变更什么时候生效？"}, "faq_query"),
    ("当前套餐", {"user_id": "u1001", "session_id": "demo-check-package", "role": "user", "message": "查询我的当前套餐"}, "package_query"),
    ("账单异常", {"user_id": "u1001", "session_id": "demo-check-bill", "role": "user", "message": "账单里为什么会有超量流量费用？"}, "bill_explain"),
    ("故障工单", {"user_id": "u1001", "session_id": "demo-check-ticket", "role": "user", "message": "我要创建工单，宽带断网"}, "ticket_create"),
    ("客服代查", {"user_id": "agent001", "session_id": "demo-check-agent", "role": "agent", "target_user_id": "u1002", "message": "帮客户查本月账单"}, "bill_query"),
]

results = []
with httpx.Client(timeout=15.0) as client:
    for name, payload, expected_intent in cases:
        response = client.post(f"{base_url}/api/chat", json=payload)
        data = response.json()
        ok = response.status_code == 200 and data.get("intent") == expected_intent and not data.get("error")
        results.append({
            "name": name,
            "ok": ok,
            "status_code": response.status_code,
            "intent": data.get("intent"),
            "trace_id": data.get("trace_id"),
            "tool_count": len(data.get("tool_calls") or []),
            "source_count": len(data.get("sources") or []),
            "error": data.get("error"),
        })

print(json.dumps({"passed": all(item["ok"] for item in results), "checks": results}, ensure_ascii=False, indent=2))
if not all(item["ok"] for item in results):
    sys.exit(1)
PY
