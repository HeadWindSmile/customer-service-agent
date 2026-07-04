param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

# 第 12 阶段脚本只封装本地启动命令，默认使用 mock/fallback，避免演示依赖外部系统。
if (-not $env:LLM_PROVIDER) { $env:LLM_PROVIDER = "mock" }
if (-not $env:MEMORY_BACKEND) { $env:MEMORY_BACKEND = "memory" }
if (-not $env:EVENT_PRODUCER) { $env:EVENT_PRODUCER = "mock" }

python -m uvicorn app.main:app --host $BindHost --port $Port --reload
