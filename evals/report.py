import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_reports(summary: dict[str, Any], results: list[dict[str, Any]], output_dir: str | Path) -> dict[str, str]:
    """输出 JSON 和 Markdown 报告。

    JSON 便于自动化读取，Markdown 便于面试演示和人工快速扫结果。
    """

    report_dir = Path(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
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
        f"- 用例数：{summary['total_cases']}",
        f"- 意图准确率：{summary['intent_accuracy']}",
        f"- 关键词命中率：{summary['answer_contains_expected_keywords']}",
        f"- Source 召回率：{summary['source_recall_rate']}",
        f"- 工具调用准确率：{summary['tool_call_accuracy']}",
        f"- 安全动作准确率：{summary['safety_expected_action_accuracy']}",
        f"- 简化幻觉率：{summary['hallucination_rate']}",
        f"- 平均延迟：{summary['avg_latency_ms']} ms",
        "",
        "| case_id | intent | expected_intent | keyword | source | tool | safety | latency_ms | trace_id |",
        "|---|---|---|---|---|---|---|---:|---|",
    ]
    for item in payload["cases"]:
        lines.append(
            "| {case_id} | {intent} | {expected_intent} | {keyword} | {source} | {tool} | {safety} | {latency} | {trace_id} |".format(
                case_id=item.get("case_id"),
                intent=item.get("intent"),
                expected_intent=item.get("expected_intent"),
                keyword=_mark(item.get("answer_contains_expected_keywords")),
                source=_mark(item.get("source_pass")),
                tool=_mark(item.get("tool_pass")),
                safety=_mark(item.get("safety_pass")),
                latency=item.get("latency_ms"),
                trace_id=item.get("trace_id"),
            )
        )
    lines.append("")
    lines.append("说明：简化幻觉率只用于本地 Demo，主要检测需要知识库来源的用例是否缺少 sources 或缺少预期关键词。")
    return "\n".join(lines)


def _mark(value: object) -> str:
    return "PASS" if value else "FAIL"
