#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

# 演示前检查只验证核心链路，不替代 pytest、离线评测或本地压测。
python scripts/smoke_test.py --base-url "$BASE_URL"
python scripts/final_demo_check.py --base-url "$BASE_URL"
