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


def test_mock_business_client_keeps_local_fallback_runnable():
    client = MockBusinessClient()

    result = asyncio.run(client.query_bill("u1001", "本月"))

    assert result["amount"] == 156.8
