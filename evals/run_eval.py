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


DEFAULT_DATASET = Path(__file__).resolve().parent / "datasets" / "customer_qa_eval.jsonl"
DEFAULT_REPORT_DIR = Path(__file__).resolve().parent / "reports"


def load_dataset(path: str | Path) -> list[dict[str, Any]]:
    dataset_path = Path(path)
    cases: list[dict[str, Any]] = []
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        cases.append(json.loads(line))
    return cases


def run_eval(base_url: str, dataset_path: str | Path, report_dir: str | Path, timeout: float = 10.0) -> dict[str, Any]:
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
            results.append(evaluate_case(case, response.json()))

    summary = summarize_results(results)
    paths = write_reports(summary, results, report_dir)
    return {"summary": summary, "report_paths": paths, "cases": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="运行第十阶段 AI 客服离线评测。")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="本地 AI 服务地址。")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="JSONL 评测数据集路径。")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="评测报告输出目录。")
    parser.add_argument("--timeout", type=float, default=10.0, help="单次请求超时时间。")
    args = parser.parse_args()
    result = run_eval(args.base_url, args.dataset, args.report_dir, args.timeout)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"JSON 报告：{result['report_paths']['json']}")
    print(f"Markdown 报告：{result['report_paths']['markdown']}")


if __name__ == "__main__":
    main()
