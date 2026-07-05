import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from evals.metrics import evaluate_case, summarize_results
from evals.report import write_reports
from evals.schema import load_dataset as load_schema_dataset


DEFAULT_DATASET = Path(__file__).resolve().parent / "datasets" / "customer_qa_eval.jsonl"
DEFAULT_REPORT_DIR = Path(__file__).resolve().parent / "reports"


def load_dataset(path: str | Path) -> list[dict[str, Any]]:
    return load_schema_dataset(path)


def run_eval(
    base_url: str,
    dataset_path: str | Path,
    report_dir: str | Path,
    timeout: float = 10.0,
    include_trace: bool = True,
) -> dict[str, Any]:
    cases = load_dataset(dataset_path)
    results: list[dict[str, Any]] = []
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout) as client:
        for index, case in enumerate(cases, start=1):
            payload = {
                "user_id": case.get("user_id", "u1001"),
                "session_id": case.get("session_id", f"eval-{case.get('id', index)}"),
                "role": case.get("role", "user"),
                "message": case["question"],
            }
            if case.get("target_user_id"):
                payload["target_user_id"] = case["target_user_id"]
            response = client.post("/api/chat", json=payload)
            response.raise_for_status()
            response_payload = response.json()
            trace = _fetch_trace(client, response_payload.get("trace_id")) if include_trace else None
            results.append(evaluate_case(case, response_payload, trace))

    summary = summarize_results(results)
    paths = write_reports(summary, results, report_dir, dataset_path=str(dataset_path))
    return {"summary": summary, "report_paths": paths, "cases": results}


def _fetch_trace(client: httpx.Client, trace_id: str | None) -> dict[str, Any] | None:
    """尽力读取 trace；trace 不可用不影响离线评测主体。"""

    if not trace_id:
        return None
    try:
        response = client.get(f"/api/traces/{trace_id}")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 AI 客服本地离线评测并生成最终演示报告。")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="本地 AI 服务地址。")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="JSONL 评测数据集路径。")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="评测报告输出目录。")
    parser.add_argument("--timeout", type=float, default=10.0, help="单次请求超时时间。")
    parser.add_argument("--no-trace", dest="include_trace", action="store_false", help="只使用 /api/chat 响应生成报告。")
    args = parser.parse_args()
    result = run_eval(args.base_url, args.dataset, args.report_dir, args.timeout, args.include_trace)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"JSON 报告：{result['report_paths']['json']}")
    print(f"Markdown 报告：{result['report_paths']['markdown']}")


if __name__ == "__main__":
    main()
