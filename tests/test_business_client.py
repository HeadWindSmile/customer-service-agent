import asyncio

import httpx
import pytest

from app.tools.business_client import BusinessClientError, HttpBusinessClient, MockBusinessClient
from mock_business_service.main import app as business_app


def _http_client() -> HttpBusinessClient:
    transport = httpx.ASGITransport(app=business_app)
    return HttpBusinessClient("http://business.test", timeout_ms=800, transport=transport)


def test_http_business_client_queries_package_through_internal_api():
    client = _http_client()

    result = asyncio.run(client.query_user_package("u1001"))

    assert result["package_name"] == "5G畅享套餐"
    assert result["monthly_fee"] == 129


def test_http_business_client_queries_offers_through_internal_api():
    client = _http_client()

    result = asyncio.run(client.query_available_offers("u1001"))

    assert result["offers"]
    assert result["offers"][0]["offer_id"].startswith("OFF-")


def test_http_business_client_recommends_offers_through_internal_api():
    client = _http_client()

    result = asyncio.run(client.recommend_offers("u1001", need="流量不够用", budget=20))

    assert result["offers"][0]["offer_id"] == "OFF-DATA-20G"


def test_http_business_client_queries_order_through_internal_api():
    client = _http_client()

    result = asyncio.run(client.query_order("u1001", "ORD-20260701001"))

    assert result["order_id"] == "ORD-20260701001"
    assert result["status"] == "processing"


def test_http_business_client_maps_business_404_to_client_error():
    client = _http_client()

    with pytest.raises(BusinessClientError) as exc_info:
        asyncio.run(client.query_bill("u1001", "2099-01"))

    assert exc_info.value.error_code == "BILL_NOT_FOUND"
    assert exc_info.value.status_code == 404
    assert "账单不存在" in exc_info.value.message


def test_http_business_client_handles_timeout_as_retriable_error():
    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    client = HttpBusinessClient(
        "http://business.test",
        timeout_ms=1,
        transport=httpx.MockTransport(timeout_handler),
    )

    with pytest.raises(BusinessClientError) as exc_info:
        asyncio.run(client.query_user_package("u1001"))

    assert exc_info.value.error_code == "BUSINESS_TIMEOUT"
    assert exc_info.value.retriable is True


def test_http_business_client_handles_service_unavailable():
    async def unavailable_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    client = HttpBusinessClient(
        "http://business.test",
        timeout_ms=800,
        transport=httpx.MockTransport(unavailable_handler),
    )

    with pytest.raises(BusinessClientError) as exc_info:
        asyncio.run(client.query_user_package("u1001"))

    assert exc_info.value.error_code == "BUSINESS_SERVICE_UNAVAILABLE"
    assert exc_info.value.retriable is True


def test_http_business_client_reuses_async_client_for_connection_pool():
    client = _http_client()

    async def scenario():
        await client.query_user_package("u1001")
        first_client = client._client
        await client.query_bill("u1001", "本月")
        return first_client

    first_client = asyncio.run(scenario())
    assert first_client is not None
    assert client._client is first_client


def test_http_business_client_retries_retriable_read_request():
    calls = {"count": 0}

    async def flaky_handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(500, json={"detail": {"error_code": "TEMP", "message": "临时失败"}})
        return httpx.Response(
            200,
            json={"package_name": "5G畅享套餐", "monthly_fee": 129, "data_quota": "60GB"},
        )

    client = HttpBusinessClient(
        "http://business.test",
        timeout_ms=800,
        transport=httpx.MockTransport(flaky_handler),
        retry_attempts=2,
        retry_backoff_ms=1,
    )

    result = asyncio.run(client.query_user_package("u1001"))

    assert result["package_name"] == "5G畅享套餐"
    assert calls["count"] == 2


def test_http_business_client_opens_simple_circuit_after_failures():
    async def unavailable_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    client = HttpBusinessClient(
        "http://business.test",
        timeout_ms=800,
        transport=httpx.MockTransport(unavailable_handler),
        retry_attempts=1,
        circuit_failure_threshold=1,
        circuit_reset_seconds=30,
    )

    with pytest.raises(BusinessClientError) as first_error:
        asyncio.run(client.query_user_package("u1001"))
    with pytest.raises(BusinessClientError) as second_error:
        asyncio.run(client.query_user_package("u1001"))

    assert first_error.value.error_code == "BUSINESS_SERVICE_UNAVAILABLE"
    assert second_error.value.error_code == "BUSINESS_CIRCUIT_OPEN"


def test_mock_business_client_keeps_local_fallback_runnable():
    client = MockBusinessClient()

    result = asyncio.run(client.query_bill("u1001", "本月"))

    assert result["amount"] == 156.8


def test_mock_business_client_supports_phase16_offer_and_order_fallback():
    client = MockBusinessClient()

    offers = asyncio.run(client.recommend_offers("u1001", need="流量不够用", budget=20))
    order = asyncio.run(client.query_order("u1001", "ORD-20260701001"))

    assert offers["offers"][0]["offer_id"] == "OFF-DATA-20G"
    assert order["order_id"] == "ORD-20260701001"
