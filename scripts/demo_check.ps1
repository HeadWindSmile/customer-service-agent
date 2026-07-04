param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

# 演示前检查只验证核心链路，不替代 pytest 或离线评测。
python scripts/smoke_test.py --base-url $BaseUrl

$cases = @(
    @{
        name = "套餐规则"
        expected_intent = "faq_query"
        payload = @{ user_id = "u1001"; session_id = "demo-check-faq"; role = "user"; message = "套餐变更什么时候生效？" }
    },
    @{
        name = "当前套餐"
        expected_intent = "package_query"
        payload = @{ user_id = "u1001"; session_id = "demo-check-package"; role = "user"; message = "查询我的当前套餐" }
    },
    @{
        name = "账单异常"
        expected_intent = "bill_explain"
        payload = @{ user_id = "u1001"; session_id = "demo-check-bill"; role = "user"; message = "账单里为什么会有超量流量费用？" }
    },
    @{
        name = "故障工单"
        expected_intent = "ticket_create"
        payload = @{ user_id = "u1001"; session_id = "demo-check-ticket"; role = "user"; message = "我要创建工单，宽带断网" }
    },
    @{
        name = "客服代查"
        expected_intent = "bill_query"
        payload = @{ user_id = "agent001"; session_id = "demo-check-agent"; role = "agent"; target_user_id = "u1002"; message = "帮客户查本月账单" }
    }
)

$results = @()
foreach ($case in $cases) {
    $body = $case.payload | ConvertTo-Json -Compress
    $response = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/chat" -ContentType "application/json" -Body $body
    $ok = ($response.intent -eq $case.expected_intent) -and (-not $response.error)
    $results += [pscustomobject]@{
        name = $case.name
        ok = $ok
        intent = $response.intent
        trace_id = $response.trace_id
        tool_count = @($response.tool_calls).Count
        source_count = @($response.sources).Count
        error = $response.error
    }
}

$passed = -not ($results | Where-Object { -not $_.ok })
[pscustomobject]@{
    passed = $passed
    checks = $results
} | ConvertTo-Json -Depth 6

if (-not $passed) {
    exit 1
}
