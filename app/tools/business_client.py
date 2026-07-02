import asyncio
from abc import ABC, abstractmethod
from copy import deepcopy
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
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_ms / 1000
        self.transport = transport

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
        attempts = 2 if retry else 1
        for index in range(attempts):
            try:
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=self.timeout_seconds,
                    transport=self.transport,
                ) as client:
                    response = await client.request(method, path, params=params, json=json)
                if response.status_code >= 500 and index + 1 < attempts:
                    await asyncio.sleep(0.05)
                    continue
                if response.status_code >= 400:
                    raise self._build_error(response)
                return response.json()
            except httpx.TimeoutException as exc:
                if index + 1 < attempts:
                    await asyncio.sleep(0.05)
                    continue
                raise BusinessClientError(
                    "业务服务调用超时。",
                    error_code="BUSINESS_TIMEOUT",
                    retriable=True,
                ) from exc
            except httpx.TransportError as exc:
                if index + 1 < attempts:
                    await asyncio.sleep(0.05)
                    continue
                raise BusinessClientError(
                    "业务服务暂不可用。",
                    error_code="BUSINESS_SERVICE_UNAVAILABLE",
                    retriable=True,
                ) from exc
        raise BusinessClientError("业务服务调用失败。", retriable=True)

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
