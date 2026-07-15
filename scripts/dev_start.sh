#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# 第 12 阶段脚本只封装本地启动命令，默认使用 mock/fallback，避免演示依赖外部系统。
export LLM_PROVIDER="${LLM_PROVIDER:-mock}"
export MEMORY_BACKEND="${MEMORY_BACKEND:-memory}"
export EVENT_PRODUCER="${EVENT_PRODUCER:-mock}"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

python -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
