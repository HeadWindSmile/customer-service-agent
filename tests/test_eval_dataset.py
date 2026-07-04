import pytest

from evals.schema import load_dataset, normalize_case


def test_load_dataset_normalizes_phase15_fields(tmp_path):
    dataset = tmp_path / "eval.jsonl"
    dataset.write_text(
        '{"id":"faq","question":"套餐变更什么时候生效？","expected_intent":"faq_query",'
        '"expected_sources":["package_policy"],"expected_top_k":3}\n',
        encoding="utf-8",
    )

    cases = load_dataset(dataset)

    assert cases[0]["scenario"] == "faq"
    assert cases[0]["tags"] == ["rag", "faq"]
    assert cases[0]["expected_sources"] == [{"doc_id": "package_policy", "content_keywords": []}]
    assert cases[0]["source_required"] is True
    assert cases[0]["expected_top_k"] == 3


def test_normalize_case_keeps_phase10_dataset_compatible():
    case = normalize_case(
        {
            "id": "package-query",
            "question": "查询我的当前套餐",
            "expected_intent": "package_query",
            "expected_tool": "query_user_package",
            "should_have_sources": False,
        }
    )

    assert case["scenario"] == "tool"
    assert case["tool_required"] is True
    assert case["source_required"] is False
    assert case["expected_tool_success"] is True


def test_load_dataset_rejects_invalid_expected_top_k(tmp_path):
    dataset = tmp_path / "eval.jsonl"
    dataset.write_text('{"id":"bad","question":"q","expected_top_k":0}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="expected_top_k"):
        load_dataset(dataset)
