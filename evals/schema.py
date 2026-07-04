import json
from pathlib import Path
from typing import Any


VALID_SCENARIOS = {"faq", "bill_explain", "fault_diagnosis", "tool", "safety"}


def load_dataset(path: str | Path) -> list[dict[str, Any]]:
    """加载并规范化 JSONL 评测集。

    第 15 阶段仍保留 JSONL，是为了让面试 Demo 可以直接读写小样本；这里集中做
    schema 兼容和默认值填充，避免 runner、metrics、report 各自理解一套字段。
    """

    dataset_path = Path(path)
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{dataset_path}:{line_number} 不是合法 JSONL：{exc}") from exc
        cases.append(normalize_case(raw, line_number=line_number))
    return cases


def normalize_case(case: dict[str, Any], *, line_number: int | None = None) -> dict[str, Any]:
    """把旧版第 10 阶段字段升级成第 15 阶段统一形态。"""

    normalized = dict(case)
    location = f"第 {line_number} 行" if line_number else "评测用例"
    if not str(normalized.get("id", "")).strip():
        raise ValueError(f"{location} 缺少 id")
    if not str(normalized.get("question", "")).strip():
        raise ValueError(f"{location} 缺少 question")

    normalized["scenario"] = _normalize_scenario(normalized)
    normalized["tags"] = _normalize_tags(normalized)
    normalized["expected_sources"] = _normalize_expected_sources(normalized.get("expected_sources"))
    normalized["expected_top_k"] = _normalize_expected_top_k(normalized.get("expected_top_k"))
    normalized["expected_rerank"] = _normalize_expected_rerank(normalized.get("expected_rerank"))
    normalized["expected_keywords"] = _normalize_string_list(normalized.get("expected_keywords"))
    normalized["forbidden_answer_keywords"] = _normalize_string_list(normalized.get("forbidden_answer_keywords"))
    normalized["source_required"] = bool(
        normalized.get(
            "source_required",
            normalized.get("should_have_sources", bool(normalized["expected_sources"])),
        )
    )
    normalized["should_have_sources"] = normalized["source_required"]
    normalized["tool_required"] = bool(normalized.get("tool_required", bool(normalized.get("expected_tool"))))
    normalized.setdefault("expected_tool_success", True if normalized.get("expected_tool") else None)
    normalized.setdefault("safety_expected_action", "allow")
    normalized.setdefault("role", "user")
    return normalized


def _normalize_scenario(case: dict[str, Any]) -> str:
    scenario = str(case.get("scenario") or "").strip()
    if scenario in VALID_SCENARIOS:
        return scenario
    if case.get("risk_case") or case.get("safety_expected_action") in {"block", "review"}:
        return "safety"
    if case.get("expected_tool") or case.get("tool_required"):
        return "tool"
    expected_intent = str(case.get("expected_intent") or "")
    if expected_intent in {"bill_explain"}:
        return "bill_explain"
    if expected_intent in {"fault_diagnosis"}:
        return "fault_diagnosis"
    return "faq"


def _normalize_tags(case: dict[str, Any]) -> list[str]:
    tags = case.get("tags")
    if isinstance(tags, str):
        return [tags]
    if isinstance(tags, list):
        return [str(item) for item in tags if str(item).strip()]
    scenario = _normalize_scenario(case)
    if scenario == "tool":
        return ["tool"]
    if scenario == "safety":
        return ["safety"]
    return ["rag", scenario]


def _normalize_expected_sources(value: Any) -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError("expected_sources 必须是列表")
    sources: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            sources.append({"doc_id": item, "content_keywords": []})
            continue
        if not isinstance(item, dict):
            raise ValueError("expected_sources 中的元素必须是字符串或对象")
        source = dict(item)
        source["content_keywords"] = _normalize_string_list(source.get("content_keywords"))
        sources.append(source)
    return sources


def _normalize_expected_top_k(value: Any) -> int:
    if value in (None, ""):
        return 3
    try:
        top_k = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("expected_top_k 必须是正整数") from exc
    if top_k <= 0:
        raise ValueError("expected_top_k 必须大于 0")
    return top_k


def _normalize_expected_rerank(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, bool):
        return {"reranker_used": value}
    if not isinstance(value, dict):
        raise ValueError("expected_rerank 必须是对象")
    return dict(value)


def _normalize_string_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        raise ValueError("字符串列表字段必须是字符串或列表")
    return [str(item) for item in value if str(item).strip()]
