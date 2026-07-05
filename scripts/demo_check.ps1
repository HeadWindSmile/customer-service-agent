param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

# 演示前检查只验证核心链路，不替代 pytest、离线评测或本地压测。
python scripts/smoke_test.py --base-url $BaseUrl
python scripts/final_demo_check.py --base-url $BaseUrl
