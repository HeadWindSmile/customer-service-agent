from app.observability.trace_repository import TraceRepository
from app.observability.tracing import (
    TraceContext,
    add_attribute,
    add_event,
    get_current_trace_id,
    reset_current_trace,
    set_current_trace,
)


def test_trace_context_records_span_event_and_attribute():
    trace = TraceContext.new()
    span = trace.start_span("unit.test", {"phase": "start"})
    trace.add_attribute("intent", "faq_query")
    trace.add_event("unit.event", {"ok": True})
    trace.end_span(span)
    trace.finish()

    data = trace.to_dict()

    assert data["trace_id"] == trace.trace_id
    assert data["attributes"]["intent"] == "faq_query"
    assert data["spans"][0]["name"] == "unit.test"
    assert data["spans"][0]["latency_ms"] >= 0
    assert data["events"][0]["name"] == "unit.event"


def test_context_var_sets_and_resets_current_trace():
    trace = TraceContext.new()
    token = set_current_trace(trace)

    add_attribute("memory_backend", "memory")
    add_event("context.event", {"trace": "current"})

    assert get_current_trace_id() == trace.trace_id
    assert trace.attributes["memory_backend"] == "memory"
    assert trace.events[-1].name == "context.event"

    reset_current_trace(token)

    assert get_current_trace_id() == ""


def test_trace_repository_saves_and_loads_trace(tmp_path):
    trace = TraceContext.new()
    trace.add_attribute("intent", "package_query")
    trace.finish()
    repository = TraceRepository(storage_dir=str(tmp_path))

    saved = repository.save(trace)
    loaded = repository.get(trace.trace_id)

    assert saved is True
    assert loaded is not None
    assert loaded["trace_id"] == trace.trace_id
    assert loaded["attributes"]["intent"] == "package_query"
