import json

from evals.report import write_reports


def test_write_reports_outputs_json_and_markdown_with_metric_boundaries(tmp_path):
    summary = {
        "total_cases": 1,
        "intent_accuracy": 1.0,
        "top1_hit_rate": 1.0,
        "top3_hit_rate": 1.0,
        "topk_hit_rate": 1.0,
        "source_coverage_avg": 1.0,
        "rerank_expectation_accuracy": 1.0,
        "tool_call_accuracy": 1.0,
        "safety_action_accuracy": 1.0,
        "hallucination_rate": 0.0,
        "avg_latency_ms": 10.0,
        "p95_latency_ms": 10.0,
        "total_tokens": 12,
        "total_estimated_cost": 0.0,
        "by_scenario": {"faq": {"total_cases": 1, "intent_accuracy": 1.0}},
    }
    results = [
        {
            "case_id": "faq",
            "scenario": "faq",
            "intent": "faq_query",
            "expected_intent": "faq_query",
            "expected_source_count": 1,
            "top1_hit": True,
            "top3_hit": True,
            "topk_hit": True,
            "source_coverage": 1.0,
            "rerank_evaluated": True,
            "rerank_pass": True,
            "tool_pass": True,
            "safety_pass": True,
            "hallucination_flag": False,
            "latency_ms": 10.0,
            "trace_id": "trace-test",
        }
    ]

    paths = write_reports(summary, results, tmp_path, dataset_path="evals/datasets/customer_qa_eval.jsonl")

    payload = json.loads((tmp_path / "latest_report.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "latest_report.md").read_text(encoding="utf-8")

    assert paths["json"].endswith("latest_report.json")
    assert payload["metric_scope"] == "local_demo_eval"
    assert "production_metric_definitions" in payload
    assert "本地 Demo 评测结果" in markdown
    assert "生产项目指标口径说明" in markdown
    assert "不代表生产项目历史指标" in markdown
