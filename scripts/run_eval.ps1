param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string[]]$EvalArgs = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

python evals/run_eval.py --base-url $BaseUrl @EvalArgs
