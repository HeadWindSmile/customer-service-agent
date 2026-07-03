from app.events.event_schema import Event
from app.events.event_type import EventType


def test_event_schema_has_required_fields_and_json_values():
    event = Event(
        event_type=EventType.AI_QA_FINISHED,
        trace_id="trace-test",
        user_id="u1001",
        session_id="session-test",
        payload={"intent": "faq_query", "latency_ms": 12.5},
    )

    data = event.to_json_dict()

    assert data["event_id"]
    assert data["event_type"] == "AI_QA_FINISHED"
    assert data["trace_id"] == "trace-test"
    assert data["user_id"] == "u1001"
    assert data["session_id"] == "session-test"
    assert data["payload"]["intent"] == "faq_query"
    assert data["created_at"]


def test_event_type_contains_phase9_events():
    assert EventType.TICKET_CREATED.value == "TICKET_CREATED"
    assert EventType.AUDIT_LOG_CREATED.value == "AUDIT_LOG_CREATED"
    assert EventType.AI_QA_FINISHED.value == "AI_QA_FINISHED"
    assert EventType.SAFETY_REVIEW_REQUIRED.value == "SAFETY_REVIEW_REQUIRED"
    assert EventType.USER_FEEDBACK_CREATED.value == "USER_FEEDBACK_CREATED"
