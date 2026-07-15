import asyncio
from abc import ABC, abstractmethod
from copy import deepcopy
from time import monotonic
from typing import Any
from uuid import uuid4

import httpx

from app.config import settings
from app.observability.metrics import metrics_recorder


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

    @abstractmethod
    async def query_available_offers(self, user_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def recommend_offers(
        self,
        user_id: str,
        need: str | None = None,
        budget: float | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def query_order(self, user_id: str, order_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def query_recent_orders(self, user_id: str, limit: int = 3) -> dict[str, Any]:
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
        self._offers = {
            "OFF-DATA-20G": {
                "offer_id": "OFF-DATA-20G",
                "name": "20GB 流量加油包优惠",
                "offer_type": "data_booster",
                "description": "适合本月流量经常不够用的用户，办理后立即生效。",
                "benefits": ["每月额外 20GB 国内通用流量", "首月按天折算"],
                "monthly_fee_delta": 19.0,
                "valid_until": "2026-12-31",
                "eligible_levels": ["gold", "standard"],
                "applicable_packages": ["5G畅享套餐", "基础套餐"],
                "tags": ["流量", "data", "高性价比"],
                "recommend_reason": "匹配流量不够用诉求，月增费用较低。",
            },
            "OFF-MEMBER-VIDEO": {
                "offer_id": "OFF-MEMBER-VIDEO",
                "name": "视频会员权益包",
                "offer_type": "member_benefit",
                "description": "面向金卡用户开放的视频会员权益优惠。",
                "benefits": ["月度视频会员权益", "权益到期前短信提醒"],
                "monthly_fee_delta": 15.0,
                "valid_until": "2026-10-31",
                "eligible_levels": ["gold"],
                "applicable_packages": ["5G畅享套餐", "家庭融合套餐"],
                "tags": ["权益", "会员", "video"],
                "recommend_reason": "匹配权益类诉求，当前用户等级可办理。",
            },
            "OFF-FAMILY-BUNDLE": {
                "offer_id": "OFF-FAMILY-BUNDLE",
                "name": "家庭融合权益升级",
                "offer_type": "family_bundle",
                "description": "适合多成员共享流量和宽带权益的家庭用户。",
                "benefits": ["家庭成员共享流量池", "宽带提速权益"],
                "monthly_fee_delta": 39.0,
                "valid_until": "2026-09-30",
                "eligible_levels": ["gold"],
                "applicable_packages": ["家庭融合套餐", "5G畅享套餐"],
                "tags": ["家庭", "宽带", "融合"],
                "recommend_reason": "匹配家庭共享和宽带权益诉求。",
            },
        }
        self._orders = {
            "ORD-20260701001": {
                "order_id": "ORD-20260701001",
                "user_id": "u1001",
                "order_type": "offer_subscribe",
                "title": "20GB 流量加油包优惠办理",
                "status": "processing",
                "created_at": "2026-07-01T10:15:00+08:00",
                "updated_at": "2026-07-01T10:20:00+08:00",
                "related_resource_id": "OFF-DATA-20G",
                "can_cancel": True,
                "summary": "订单已受理，权益预计 10 分钟内生效。",
            },
            "PKG-20260630001": {
                "order_id": "PKG-20260630001",
                "user_id": "u1001",
                "order_type": "package_change",
                "title": "5G畅享套餐变更",
                "status": "completed",
                "created_at": "2026-06-30T18:30:00+08:00",
                "updated_at": "2026-07-01T00:05:00+08:00",
                "related_resource_id": "5G畅享套餐",
                "can_cancel": False,
                "summary": "套餐变更已完成，当前套餐为 5G畅享套餐。",
            },
            "ORD-20260702002": {
                "order_id": "ORD-20260702002",
                "user_id": "u1002",
                "order_type": "ticket_service",
                "title": "宽带售后服务单",
                "status": "processing",
                "created_at": "2026-07-02T09:00:00+08:00",
                "updated_at": "2026-07-02T11:30:00+08:00",
                "related_resource_id": "TCK-ABC123456",
                "can_cancel": False,
                "summary": "售后专员正在跟进，预计 24 小时内反馈。",
            },
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
        order_id = f"PKG-{uuid4().hex[:10].upper()}"
        self._orders[order_id] = {
            "order_id": order_id,
            "user_id": user_id,
            "order_type": "package_change",
            "title": f"{target_package} 变更申请",
            "status": "submitted",
            "created_at": "2026-07-04T12:00:00+08:00",
            "updated_at": "2026-07-04T12:00:00+08:00",
            "related_resource_id": target_package,
            "can_cancel": True,
            "summary": "套餐变更申请已提交，生效时间以业务系统确认为准。",
        }
        return {
            "order_id": order_id,
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

    async def query_available_offers(self, user_id: str) -> dict[str, Any]:
        if user_id not in self._profiles:
            raise BusinessClientError("用户不存在。", error_code="USER_NOT_FOUND", status_code=404)
        return {"offers": self._available_offer_list(user_id)}

    async def recommend_offers(
        self,
        user_id: str,
        need: str | None = None,
        budget: float | None = None,
    ) -> dict[str, Any]:
        if user_id not in self._profiles:
            raise BusinessClientError("用户不存在。", error_code="USER_NOT_FOUND", status_code=404)
        offers = self._available_offer_list(user_id)
        if budget is not None:
            offers = [offer for offer in offers if float(offer["monthly_fee_delta"]) <= budget]
        tokens = _offer_need_tokens(need or "")
        if tokens:
            scored: list[tuple[int, dict[str, Any]]] = []
            for offer in offers:
                text = " ".join([offer["name"], offer["description"], " ".join(offer.get("tags", []))]).lower()
                scored.append((sum(1 for token in tokens if token.lower() in text), offer))
            matched = [offer for score, offer in sorted(scored, key=lambda item: item[0], reverse=True) if score > 0]
            offers = matched or offers
        return {"offers": offers[:3]}

    async def query_order(self, user_id: str, order_id: str) -> dict[str, Any]:
        if user_id not in self._profiles:
            raise BusinessClientError("用户不存在。", error_code="USER_NOT_FOUND", status_code=404)
        order = self._orders.get(order_id.upper())
        if not order or order.get("user_id") != user_id:
            raise BusinessClientError("订单不存在或不属于当前用户。", error_code="ORDER_NOT_FOUND", status_code=404)
        return deepcopy(order)

    async def query_recent_orders(self, user_id: str, limit: int = 3) -> dict[str, Any]:
        if user_id not in self._profiles:
            raise BusinessClientError("用户不存在。", error_code="USER_NOT_FOUND", status_code=404)
        orders = [deepcopy(order) for order in self._orders.values() if order.get("user_id") == user_id]
        orders.sort(key=lambda order: order.get("created_at", ""), reverse=True)
        return {"orders": orders[: max(1, limit)]}

    def _available_offer_list(self, user_id: str) -> list[dict[str, Any]]:
        profile = self._profiles[user_id]
        package = self._packages.get(user_id)
        if not package:
            return []
        level = profile.get("level", "")
        package_name = package.get("package_name", "")
        offers = []
        for offer in self._offers.values():
            if level not in offer.get("eligible_levels", []):
                continue
            if package_name not in offer.get("applicable_packages", []):
                continue
            offers.append(_public_offer(offer))
        return offers


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

    async def query_available_offers(self, user_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/internal/users/{user_id}/offers", retry=True)

    async def recommend_offers(
        self,
        user_id: str,
        need: str | None = None,
        budget: float | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"need": need}
        if budget is not None:
            payload["budget"] = budget
        return await self._request("POST", f"/internal/users/{user_id}/offers/recommend", json=payload)

    async def query_order(self, user_id: str, order_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/internal/users/{user_id}/orders/{order_id}", retry=True)

    async def query_recent_orders(self, user_id: str, limit: int = 3) -> dict[str, Any]:
        return await self._request("GET", f"/internal/users/{user_id}/orders", params={"limit": limit}, retry=True)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        retry: bool = False,
    ) -> dict[str, Any]:
        operation = _operation_name(method, path)
        started = monotonic()
        client_type = type(self).__name__
        if self._is_circuit_open():
            metrics_recorder.record_business_client_circuit_open(operation=operation, client_type=client_type)
            metrics_recorder.record_business_client_request(
                operation=operation,
                client_type=client_type,
                result="circuit_open",
                latency_ms=_elapsed_since_ms(started),
                error_code="BUSINESS_CIRCUIT_OPEN",
            )
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
                    metrics_recorder.record_business_client_retry(operation=operation, client_type=client_type)
                    await self._sleep_before_retry(index)
                    continue
                if response.status_code >= 400:
                    if response.status_code >= 500:
                        self._record_failure()
                    error = self._build_error(response)
                    metrics_recorder.record_business_client_request(
                        operation=operation,
                        client_type=client_type,
                        result="error",
                        latency_ms=_elapsed_since_ms(started),
                        error_code=error.error_code,
                        status_code=response.status_code,
                    )
                    raise error
                self._record_success()
                metrics_recorder.record_business_client_request(
                    operation=operation,
                    client_type=client_type,
                    result="success",
                    latency_ms=_elapsed_since_ms(started),
                    status_code=response.status_code,
                )
                return response.json()
            except httpx.TimeoutException as exc:
                self._record_failure()
                if index + 1 < attempts:
                    metrics_recorder.record_business_client_retry(operation=operation, client_type=client_type)
                    await self._sleep_before_retry(index)
                    continue
                metrics_recorder.record_business_client_timeout(operation=operation, client_type=client_type)
                metrics_recorder.record_business_client_request(
                    operation=operation,
                    client_type=client_type,
                    result="timeout",
                    latency_ms=_elapsed_since_ms(started),
                    error_code="BUSINESS_TIMEOUT",
                )
                raise BusinessClientError(
                    "业务服务调用超时。",
                    error_code="BUSINESS_TIMEOUT",
                    retriable=True,
                ) from exc
            except httpx.TransportError as exc:
                self._record_failure()
                if index + 1 < attempts:
                    metrics_recorder.record_business_client_retry(operation=operation, client_type=client_type)
                    await self._sleep_before_retry(index)
                    continue
                metrics_recorder.record_business_client_request(
                    operation=operation,
                    client_type=client_type,
                    result="transport_error",
                    latency_ms=_elapsed_since_ms(started),
                    error_code="BUSINESS_SERVICE_UNAVAILABLE",
                )
                raise BusinessClientError(
                    "业务服务暂不可用。",
                    error_code="BUSINESS_SERVICE_UNAVAILABLE",
                    retriable=True,
                ) from exc
        metrics_recorder.record_business_client_request(
            operation=operation,
            client_type=client_type,
            result="error",
            latency_ms=_elapsed_since_ms(started),
            error_code="BUSINESS_CLIENT_ERROR",
        )
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


def _elapsed_since_ms(started: float) -> float:
    return round((monotonic() - started) * 1000, 2)


def _operation_name(method: str, path: str) -> str:
    """把具体 URL 收敛成低基数 operation，避免用户 ID 或订单号进入指标标签。"""

    normalized = path.lower()
    if normalized.endswith("/package") and method.upper() == "GET":
        return "query_user_package"
    if normalized.endswith("/package/change"):
        return "change_package"
    if normalized.endswith("/bill"):
        return "query_bill"
    if normalized.endswith("/offers") and method.upper() == "GET":
        return "query_available_offers"
    if normalized.endswith("/offers/recommend"):
        return "recommend_offers"
    if normalized.endswith("/orders") and method.upper() == "GET":
        return "query_recent_orders"
    if "/orders/" in normalized:
        return "query_order"
    if normalized == "/internal/tickets" and method.upper() == "POST":
        return "create_ticket"
    if normalized.startswith("/internal/tickets/"):
        return "query_ticket"
    if normalized.startswith("/internal/users/") and method.upper() == "GET":
        return "query_user_profile"
    return f"{method.lower()}_business_request"


def _public_offer(offer: dict[str, Any]) -> dict[str, Any]:
    public_fields = {
        "offer_id",
        "name",
        "offer_type",
        "description",
        "benefits",
        "monthly_fee_delta",
        "valid_until",
        "tags",
        "recommend_reason",
    }
    return {key: deepcopy(value) for key, value in offer.items() if key in public_fields}


def _offer_need_tokens(need: str) -> list[str]:
    text = need.strip().lower()
    tokens = [text] if text else []
    if "流量" in text or "data" in text or "不够" in text:
        tokens.extend(["流量", "data"])
    if "会员" in text or "权益" in text or "视频" in text:
        tokens.extend(["会员", "权益", "video"])
    if "家庭" in text or "宽带" in text or "融合" in text:
        tokens.extend(["家庭", "宽带", "融合"])
    return tokens
