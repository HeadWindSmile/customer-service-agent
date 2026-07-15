import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PRODUCTION_METRIC_DEFINITIONS = {
    "topk_hit_rate": "生产口径通常基于固定人工标注评测集，统计正确知识片段是否出现在 TopK 召回结果中。",
    "source_coverage": "生产口径会按标准答案引用的知识片段集合计算覆盖率，并结合人工抽检修正标注噪声。",
    "hallucination_rate": "生产口径需要人工质检或 LLM-as-judge 辅助判定；本地 Demo 仅做规则化疑似检测。",
    "latency": "生产口径应来自网关/APM/Prometheus 等线上统计；本地报告只统计 eval 脚本请求样本。",
    "token_cost": "生产口径应以真实模型 response usage 或账单为准；本地 mock 模式只展示 estimated 字段。",
}

CAVEATS = [
    "本报告的数值只代表当前本地 Demo 评测集结果，不代表生产项目历史指标。",
    "默认 mock/fallback 模式不依赖真实 Milvus、BGE、Reranker 或真实 LLM。",
    "简化幻觉检测只检查 sources、关键词和禁用承诺词，不能替代人工质检。",
    "Token 和成本字段在 mock 模式下为估算或不可用，不是供应商账单数据。",
]


def write_reports(
    summary: dict[str, Any],
    results: list[dict[str, Any]],
    output_dir: str | Path,
    dataset_path: str | None = None,
) -> dict[str, str]:
    """输出 JSON 和 Markdown 报告。

    JSON 面向自动化消费，Markdown 面向面试讲解；两者都显式区分“本地 Demo
    评测结果”和“生产项目指标口径”，避免把生产指标写成本地结论。
    """

    report_dir = Path(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": dataset_path,
        "metric_scope": "local_demo_eval",
        "summary": summary,
        "production_metric_definitions": PRODUCTION_METRIC_DEFINITIONS,
        "caveats": CAVEATS,
        "cases": results,
    }
    json_path = report_dir / "latest_report.json"
    md_path = report_dir / "latest_report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    md_path.write_text(_markdown_report(payload), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# AI 效果评测报告",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 数据集：{payload.get('dataset_path') or '未记录'}",
        f"- 指标范围：本地 Demo 离线评测，不代表生产项目历史指标",
        "",
        "## 本地 Demo 评测结果",
        "",
        f"- 用例数：{summary.get('total_cases', 0)}",
        f"- 意图准确率：{summary.get('intent_accuracy', 0.0)}",
        f"- Top1 命中率：{summary.get('top1_hit_rate', 0.0)}",
        f"- Top3 命中率：{summary.get('top3_hit_rate', 0.0)}",
        f"- TopK 命中率：{summary.get('topk_hit_rate', 0.0)}",
        f"- Source coverage：{summary.get('source_coverage_avg', 0.0)}",
        f"- Rerank 期望准确率：{summary.get('rerank_expectation_accuracy', 0.0)}",
        f"- 工具调用准确率：{summary.get('tool_call_accuracy', 0.0)}",
        f"- 安全动作准确率：{summary.get('safety_action_accuracy', summary.get('safety_expected_action_accuracy', 0.0))}",
        f"- 简化疑似幻觉率：{summary.get('hallucination_rate', 0.0)}",
        f"- 平均延迟：{summary.get('avg_latency_ms', 0.0)} ms",
        f"- P95 延迟：{summary.get('p95_latency_ms', 0.0)} ms",
        f"- Token 总量：{summary.get('total_tokens', 0)}",
        f"- 估算成本：{summary.get('total_estimated_cost', 0.0)}",
        "",
        "## 分场景结果",
        "",
        "| scenario | cases | intent | topk | source_coverage | tool | safety | hallucination | avg_latency_ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for scenario, item in sorted((summary.get("by_scenario") or {}).items()):
        lines.append(
            "| {scenario} | {cases} | {intent} | {topk} | {coverage} | {tool} | {safety} | {hallucination} | {latency} |".format(
                scenario=scenario,
                cases=item.get("total_cases", 0),
                intent=item.get("intent_accuracy", 0.0),
                topk=item.get("topk_hit_rate", 0.0),
                coverage=item.get("source_coverage_avg", 0.0),
                tool=item.get("tool_call_accuracy", 0.0),
                safety=item.get("safety_action_accuracy", item.get("safety_expected_action_accuracy", 0.0)),
                hallucination=item.get("hallucination_rate", 0.0),
                latency=item.get("avg_latency_ms", 0.0),
            )
        )

    lines.extend(
        [
            "",
            "## 用例明细",
            "",
            "| case_id | scenario | intent | top1 | top3 | topk | coverage | rerank | tool | safety | hallucination | latency_ms | trace_id |",
            "|---|---|---|---|---|---|---:|---|---|---|---|---:|---|",
        ]
    )
    for item in payload["cases"]:
        lines.append(
            "| {case_id} | {scenario} | {intent}/{expected_intent} | {top1} | {top3} | {topk} | {coverage} | {rerank} | {tool} | {safety} | {hallucination} | {latency} | {trace_id} |".format(
                case_id=item.get("case_id"),
                scenario=item.get("scenario"),
                intent=item.get("intent"),
                expected_intent=item.get("expected_intent"),
                top1=_mark(item.get("top1_hit")) if item.get("expected_source_count") else "N/A",
                top3=_mark(item.get("top3_hit")) if item.get("expected_source_count") else "N/A",
                topk=_mark(item.get("topk_hit")) if item.get("expected_source_count") else "N/A",
                coverage=item.get("source_coverage"),
                rerank=_mark(item.get("rerank_pass")) if item.get("rerank_evaluated") else "N/A",
                tool=_mark(item.get("tool_pass")),
                safety=_mark(item.get("safety_pass")),
                hallucination="YES" if item.get("hallucination_flag") else "NO",
                latency=item.get("latency_ms"),
                trace_id=item.get("trace_id"),
            )
        )

    lines.extend(
        [
            "",
            "## 生产项目指标口径说明",
            "",
        ]
    )
    for name, description in payload["production_metric_definitions"].items():
        lines.append(f"- `{name}`：{description}")

    lines.extend(
        [
            "",
            "## 边界说明",
            "",
        ]
    )
    for caveat in payload["caveats"]:
        lines.append(f"- {caveat}")
    lines.append("")
    return "\n".join(lines)


def _mark(value: object) -> str:
    return "PASS" if value else "FAIL"
