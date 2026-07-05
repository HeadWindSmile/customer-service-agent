from app.observability.metrics import MetricsLiteRecorder


def test_metrics_recorder_keeps_metrics_lite_snapshot_compatible():
    recorder = MetricsLiteRecorder(window_size=5)

    recorder.start_request()
    recorder.record_request("GET", "/health", 200, 12.5)

    snapshot = recorder.snapshot()
    assert snapshot["total_requests"] == 1
    assert snapshot["success_requests"] == 1
    assert snapshot["paths"]["GET /health"]["avg_latency_ms"] == 12.5


def test_metrics_recorder_exports_domain_metrics_as_prometheus_text():
    recorder = MetricsLiteRecorder(window_size=5)

    recorder.record_chat_request(intent="package_query", latency_ms=30)
    recorder.record_safety_check(scope="input", action="allow", risk_level="SAFE")
    recorder.record_tool_call(tool_name="query_user_package", success=True, latency_ms=8)
    recorder.record_business_client_request(
        operation="query_user_package",
        client_type="HttpBusinessClient",
        result="success",
        latency_ms=6,
        status_code=200,
    )
    recorder.record_business_client_retry(operation="query_user_package", client_type="HttpBusinessClient")
    recorder.record_business_client_timeout(operation="query_user_package", client_type="HttpBusinessClient")
    recorder.record_business_client_circuit_open(operation="query_user_package", client_type="HttpBusinessClient")
    recorder.record_cache_event(cache_name="rag_search", result="hit", size=1)
    recorder.record_rag_retrieval(scenario="faq", cache_hit=True, source_count=2)
    recorder.record_event_publish(event_type="AI_QA_FINISHED", producer_type="MockEventProducer", success=True, latency_ms=1)

    text = recorder.prometheus_text()

    assert 'customer_service_agent_chat_requests_total{intent="package_query",result="success"} 1' in text
    assert 'customer_service_agent_safety_checks_total{action="allow",risk_level="SAFE",scope="input"} 1' in text
    assert 'customer_service_agent_tool_calls_total{success="true",tool_name="query_user_package"} 1' in text
    assert "customer_service_agent_business_client_retries_total" in text
    assert "customer_service_agent_business_client_timeouts_total" in text
    assert "customer_service_agent_business_client_circuit_open_total" in text
    assert 'customer_service_agent_cache_size{cache_name="rag_search"} 1' in text
    assert 'customer_service_agent_rag_sources_count{scenario="faq"} 2' in text
    assert "customer_service_agent_event_publish_latency_seconds_bucket" in text
