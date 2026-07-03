import asyncio
from abc import ABC, abstractmethod
from copy import deepcopy
from time import monotonic
from typing import Any
from uuid import uuid4

import httpx

from app.config import settings


class BusinessClientError(Exception):
    """业务系统调用失败。

    Router 会把该异常转换成 tool_calls 中的失败记录。这样工具层不用知道 HTTP
    框架细节，面试讲解时也能清楚说明“AI 服务只消费业务服务能力，不接触业务库”。
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "BUSINESS_CLIENT_ERROR",
        status_code: int | None = None,
        retriable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.retriable = retriable

    def to_output(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
            "retriable": self.retriable,
        }


class BusinessClient(ABC):
    """业务系统客户端抽象，隔离 mock、本地 HTTP 和未来真实 Spring Boot 服务。"""

    @abstractmethod
    async def query_user_profile(self, user_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def query_user_package(self, user_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def query_bill(self, user_id: str, month: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def change_package(self, user_id: str, target_package: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def create_ticket(self, user_id: str, issue_type: str, description: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def query_ticket(self, user_id: str, ticket_id: str) -> dict[str, Any]:
        raise NotImplementedError


class MockBusinessClient(BusinessClient):
    """本地 fallback 客户端。

    未配置业务服务地址时使用它，保证 demo 在只启动 AI 服务的情况下也能演示。
    它仍然放在 tools 边界内，Router 和 API 不直接读取任何 mock 数据。
    """

    def __init__(self) -> None:
        self._profiles = {
            "user_001": {"user_id": "user_001", "name": "演示用户", "level": "gold"},
            "u1001": {"user_id": "u1001", "name": "张先生", "level": "gold"},
            "u1002": {"user_id": "u1002", "name": "李女士", "level": "standard"},
        }
        self._available_packages = {
            "5G畅享套餐": {"package_name": "5G畅享套餐", "monthly_fee": 129, "data_quota": "60GB"},
            "基础套餐": {"package_name": "基础套餐", "monthly_fee": 59, "data_quota": "20GB"},
            "家庭融合套餐": {"package_name": "家庭融合套餐", "monthly_fee": 199, "data_quota": "100GB"},
            "校园套餐": {"package_name": "校园套餐", "monthly_fee": 39, "data_quota": "30GB"},
        }
        self._packages = {
            "user_001": deepcopy(self._available_packages["5G畅享套餐"]),
            "u1001": deepcopy(self._available_packages["5G畅享套餐"]),
            "u1002": deepcopy(self._available_packages["基础套餐"]),
        }
        self._bills = {
            ("user_001", "本月"): {"month": "本月", "amount": 156.8, "status": "已出账", "items": ["套餐月费", "流量包"]},
            ("u1001", "本月"): {"month": "本月", "amount": 156.8, "status": "已出账", "items": ["套餐月费", "流量包"]},
            ("u1002", "本月"): {"month": "本月", "amount": 68.0, "status": "已出账", "items": ["套餐月费", "语音通话"]},
        }

    async def query_user_profile(self, user_id: str) -> dict[str, Any]:
        profile = self._profiles.get(user_id)
        if not profile:
            raise BusinessClientError("用户不存在。", error_code="USER_NOT_FOUND", status_code=404)
        return deepcopy(profile)

    async def query_user_package(self, user_id: str) -> dict[str, Any]:
        package = self._packages.get(user_id)
        if not package:
            raise BusinessClientError("用户当前套餐不存在。", error_code="PACKAGE_NOT_FOUND", status_code=404)
        return deepcopy(package)

    async def query_bill(self, user_id: str, month: str) -> dict[str, Any]:
        bill = self._bills.get((user_id, month))
        if not bill:
            raise BusinessClientError("账单不存在。", error_code="BILL_NOT_FOUND", status_code=404)
        return deepcopy(bill)

    async def change_package(self, user_id: str, target_package: str) -> dict[str, Any]:
        if user_id not in self._profiles:
            raise BusinessClientError("用户不存在。", error_code="USER_NOT_FOUND", status_code=404)
        if target_package not in self._available_packages:
            raise BusinessClientError("目标套餐不存在。", error_code="TARGET_PACKAGE_NOT_FOUND", status_code=404)
        self._packages[user_id] = deepcopy(self._available_packages[target_package])
        return {
            "order_id": f"PKG-{uuid4().hex[:10].upper()}",
            "user_id": user_id,
            "target_package": target_package,
            "status": "submitted",
        }

    async def create_ticket(self, user_id: str, issue_type: str, description: str) -> dict[str, Any]:
        if user_id not in self._profiles:
            raise BusinessClientError("用户不存在。", error_code="USER_NOT_FOUND", status_code=404)
        if issue_type == "fail_create" or "模拟失败" in description:
            raise BusinessClientError("工单创建失败。", error_code="TICKET_CREATE_FAILED", status_code=500, retriable=True)
        return {
            "ticket_id": f"TCK-{uuid4().hex[:10].upper()}",
            "user_id": user_id,
            "issue_type": issue_type,
            "description": description[:120],
            "status": "created",
            "summary": "工单已创建，等待售后专员处理。",
        }

    async def query_ticket(self, user_id: str, ticket_id: str) -> dict[str, Any]:
        return {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "issue_type": "network",
            "description": "",
            "status": "processing",
            "summary": "工单已受理，售后专员正在跟进。",
        }


class HttpBusinessClient(BusinessClient):
    """通过内部 HTTP API 调用业务服务，模拟 AI 服务和 Spring Boot 的真实边界。"""

    def __init__(
        self,
        base_url: str,
        timeout_ms: int = 800,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_attempts: int | None = None,
        retry_backoff_ms: int | None = None,
        max_connections: int | None = None,
        max_keepalive_connections: int | None = None,
        circuit_breaker_enabled: bool | None = None,
        circuit_failure_threshold: int | None = None,
        circuit_reset_seconds: float | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_ms / 1000
        self.transport = transport
        self.retry_attempts = max(1, retry_attempts or settings.business_service_retry_attempts)
        self.retry_backoff_seconds = (retry_backoff_ms or settings.business_service_retry_backoff_ms) / 1000
        self.max_connections = max_connections or settings.business_service_max_connections
        self.max_keepalive_connections = (
            max_keepalive_connections or settings.business_service_max_keepalive_connections
        )
        self.circuit_breaker_enabled = (
            settings.business_service_circuit_breaker_enabled
            if circuit_breaker_enabled is None
            else circuit_breaker_enabled
        )
        self.circuit_failure_threshold = max(
            1,
            circuit_failure_threshold or settings.business_service_circuit_failure_threshold,
        )
        self.circuit_reset_seconds = circuit_reset_seconds or settings.business_service_circuit_reset_seconds
        self._client: httpx.AsyncClient | None = None
        self._failure_count = 0
        self._circuit_opened_at: float | None = None

    async def query_user_profile(self, user_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/internal/users/{user_id}", retry=True)

    async def query_user_package(self, user_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/internal/users/{user_id}/package", retry=True)

    async def query_bill(self, user_id: str, month: str) -> dict[str, Any]:
        return await self._request("GET", f"/internal/users/{user_id}/bill", params={"month": month}, retry=True)

    async def change_package(self, user_id: str, target_package: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/internal/users/{user_id}/package/change",
            json={"target_package": target_package},
        )

    async def create_ticket(self, user_id: str, issue_type: str, description: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/internal/tickets",
            json={"user_id": user_id, "issue_type": issue_type, "description": description},
        )

    async def query_ticket(self, user_id: str, ticket_id: str) -> dict[str, Any]:
        ticket = await self._request("GET", f"/internal/tickets/{ticket_id}", retry=True)
        if ticket.get("user_id") != user_id:
            raise BusinessClientError("无权查看该工单。", error_code="TICKET_FORBIDDEN", status_code=403)
        return ticket

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        retry: bool = False,
    ) -> dict[str, Any]:
        if self._is_circuit_open():
            raise BusinessClientError(
                "业务服务连续失败，短时间内已熔断。",
                error_code="BUSINESS_CIRCUIT_OPEN",
                retriable=True,
            )

        attempts = self.retry_attempts if retry else 1
        for index in range(attempts):
            try:
                client = self._get_client()
                response = await client.request(method, path, params=params, json=json)
                if response.status_code >= 500 and index + 1 < attempts:
                    self._record_failure()
                    await self._sleep_before_retry(index)
                    continue
                if response.status_code >= 400:
                    if response.status_code >= 500:
                        self._record_failure()
                    raise self._build_error(response)
                self._record_success()
                return response.json()
            except httpx.TimeoutException as exc:
                self._record_failure()
                if index + 1 < attempts:
                    await self._sleep_before_retry(index)
                    continue
                raise BusinessClientError(
                    "业务服务调用超时。",
                    error_code="BUSINESS_TIMEOUT",
                    retriable=True,
                ) from exc
            except httpx.TransportError as exc:
                self._record_failure()
                if index + 1 < attempts:
                    await self._sleep_before_retry(index)
                    continue
                raise BusinessClientError(
                    "业务服务暂不可用。",
                    error_code="BUSINESS_SERVICE_UNAVAILABLE",
                    retriable=True,
                ) from exc
        raise BusinessClientError("业务服务调用失败。", retriable=True)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_connections=self.max_connections,
                max_keepalive_connections=self.max_keepalive_connections,
            )
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
                limits=limits,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _sleep_before_retry(self, index: int) -> None:
        await asyncio.sleep(self.retry_backoff_seconds * (index + 1))

    def _record_success(self) -> None:
        self._failure_count = 0
        self._circuit_opened_at = None

    def _record_failure(self) -> None:
        if not self.circuit_breaker_enabled:
            return
        self._failure_count += 1
        if self._failure_count >= self.circuit_failure_threshold:
            self._circuit_opened_at = monotonic()

    def _is_circuit_open(self) -> bool:
        if not self.circuit_breaker_enabled or self._circuit_opened_at is None:
            return False
        if monotonic() - self._circuit_opened_at >= self.circuit_reset_seconds:
            self._failure_count = 0
            self._circuit_opened_at = None
            return False
        return True

    def _build_error(self, response: httpx.Response) -> BusinessClientError:
        error_code = f"HTTP_{response.status_code}"
        message = "业务接口调用失败。"
        try:
            payload = response.json()
            detail = payload.get("detail", payload)
            if isinstance(detail, dict):
                error_code = str(detail.get("error_code") or error_code)
                message = str(detail.get("message") or message)
            elif isinstance(detail, str):
                message = detail
        except ValueError:
            if response.text:
                message = response.text
        return BusinessClientError(
            message,
            error_code=error_code,
            status_code=response.status_code,
            retriable=response.status_code >= 500,
        )


def create_business_client() -> BusinessClient:
    if settings.business_service_base_url:
        return HttpBusinessClient(
            base_url=settings.business_service_base_url,
            timeout_ms=settings.business_service_timeout_ms,
        )
    return MockBusinessClient()
