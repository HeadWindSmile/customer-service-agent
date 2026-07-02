import json

from app.safety.review_queue import ReviewQueue
from app.safety.risk_level import RiskLevel, SafetyFinding, SafetyResult


def test_review_queue_writes_masked_jsonl_record(tmp_path):
    result = SafetyResult(
        scope="input",
        findings=[
            SafetyFinding(
                risk_type="privacy_leak",
                risk_level=RiskLevel.HIGH,
                source="regex",
                rule_id="regex_id_card",
                message="检测到身份证号。",
                evidence_masked="[身份证号已脱敏]",
            )
        ],
    )
    queue_path = tmp_path / "review_queue.jsonl"

    queued = ReviewQueue(log_path=str(queue_path)).enqueue(
        trace_id="trace-test",
        result=result,
        content="身份证110101199001011234，手机号13812345678",
    )

    assert queued is True
    record = json.loads(queue_path.read_text(encoding="utf-8").strip())
    assert record["trace_id"] == "trace-test"
    assert record["risk_level"] == "HIGH"
    assert "110101199001011234" not in record["content_masked"]
    assert "13812345678" not in record["content_masked"]
