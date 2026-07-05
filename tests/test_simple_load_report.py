import json

from scripts.simple_load_test import DISCLAIMER, build_markdown_report, write_reports


def _sample_result():
    return {
        "scenario": "mixed",
        "base_url": "http://127.0.0.1:8000",
        "concurrency": 2,
        "total_requests": 3,
        "success_requests": 2,
        "failed_requests": 1,
        "success_rate": 0.6667,
        "error_rate": 0.3333,
        "avg_latency_ms": 20.0,
        "p50_latency_ms": 18.0,
        "p95_latency_ms": 30.0,
        "max_latency_ms": 30.0,
        "duration_seconds": 1.0,
        "throughput_rps": 3.0,
        "by_intent": {"faq_query": 1, "package_query": 1, "unknown": 1},
        "by_status_code": {"200": 2, "exception": 1},
        "by_error": {"timeout": 1},
        "errors": [{"ok": False, "error": "timeout"}],
        "disclaimer": DISCLAIMER,
    }


def test_build_markdown_report_contains_phase17_metrics_and_boundary():
    markdown = build_markdown_report(_sample_result())

    assert "# 本地性能验证报告" in markdown
    assert "p50_latency_ms" in markdown
    assert "p95_latency_ms" in markdown
    assert "max_latency_ms" in markdown
    assert "error_rate" in markdown
    assert DISCLAIMER in markdown
    assert "不代表生产容量承诺" in markdown


def test_write_reports_outputs_json_and_markdown(tmp_path):
    json_path, md_path = write_reports(
        _sample_result(),
        json_report=str(tmp_path / "load.json"),
        markdown_report=str(tmp_path / "load.md"),
    )

    assert json.loads(json_path.read_text(encoding="utf-8"))["scenario"] == "mixed"
    assert "本地性能验证报告" in md_path.read_text(encoding="utf-8")
