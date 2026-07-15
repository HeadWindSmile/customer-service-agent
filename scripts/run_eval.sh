#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

python evals/run_eval.py --base-url "$BASE_URL" "$@"
