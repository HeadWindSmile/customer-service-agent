from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from app.config import settings
from app.events.event_bus import create_event_producer
from app.events.rocketmq_producer import RocketMQProducer
from app.llm.factory import create_llm_client
from app.memory.redis_memory import RedisMemory
from app.rag.embeddings import create_embedding
from app.rag.vector_store import create_vector_store


class HealthChecker:
    """集中维护健康检查逻辑。

    API 层只返回结果；具体检查放在这里，是为了避免 main.py 或 api 模块承载业务
    依赖判断，也方便面试时讲清 readiness 和普通存活检查的区别。
    """

    def __init__(self) -> None:
        self.started_at = perf_counter()

    async def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
            "env": settings.app_env,
            "uptime_seconds": round(perf_counter() - self.started_at, 2),
        }

    async def ready(self) -> dict[str, Any]:
        checks = {
            "app": self._check_app(),
            "memory": await self._check_memory(),
            "business_service": await self._check_business_service(),
            "vector_store": self._check_vector_store(),
            "llm_provider": self._check_llm_provider(),
            "event_producer": self._check_event_producer(),
            "trace_storage": self._check_trace_storage(),
        }
        ready = all(item["required"] is False or item["status"] == "ok" for item in checks.values())
        return {
            "status": "ready" if ready else "not_ready",
            "ready": ready,
            "checks": checks,
        }

    def _check_app(self) -> dict[str, Any]:
        return _ok(
            "app 基础状态正常",
            app=settings.app_name,
            version=settings.app_version,
            env=settings.app_env,
            required=True,
        )

    async def _check_memory(self) -> dict[str, Any]:
        if settings.memory_backend != "redis":
            return _ok("使用进程内 memory fallback", backend="memory", fallback_active=True, required=False)
        try:
            memory = RedisMemory()
            await _with_timeout(memory.ping(), settings.readiness_timeout_seconds)
            return _ok("Redis memory backend 可用", backend="redis", fallback_active=False, required=False)
        except Exception as exc:
            return _degraded(
                "Redis 不可用，主链路会降级到 memory fallback",
                backend="redis",
                fallback_backend="memory",
                error=str(exc),
                required=False,
            )

    async def _check_business_service(self) -> dict[str, Any]:
        if not settings.business_service_base_url:
            return _ok(
                "未配置业务服务地址，使用 MockBusinessClient fallback",
                mode="mock_fallback",
                required=False,
            )
        try:
            async with httpx.AsyncClient(
                base_url=settings.business_service_base_url.rstrip("/"),
                timeout=settings.readiness_timeout_seconds,
            ) as client:
                response = await client.get("/health")
            if response.status_code >= 400:
                return _failed(
                    "业务服务健康检查失败",
                    status_code=response.status_code,
                    required=True,
                )
            return _ok(
                "业务服务可用",
                base_url=settings.business_service_base_url,
                status_code=response.status_code,
                required=True,
            )
        except Exception as exc:
            return _failed(
                "业务服务不可用",
                base_url=settings.business_service_base_url,
                error=str(exc),
                required=True,
            )

    def _check_vector_store(self) -> dict[str, Any]:
        try:
            embedding = create_embedding(settings.embedding_provider)
            vector_store = create_vector_store(
                settings.vector_store,
                embedding,
                settings.vector_store_dir,
                settings.chroma_collection,
            )
            empty = vector_store.is_empty()
            if empty:
                return _failed(
                    "vector store 为空，RAG 知识库尚未完成加载",
                    configured_store=settings.vector_store,
                    empty=True,
                    embedding_provider=settings.embedding_provider,
                    required=True,
                )
            return _ok(
                "vector store 可访问",
                configured_store=settings.vector_store,
                empty=empty,
                embedding_provider=settings.embedding_provider,
                required=True,
            )
        except Exception as exc:
            return _failed(
                "vector store 检查失败",
                configured_store=settings.vector_store,
                error=str(exc),
                required=True,
            )

    def _check_llm_provider(self) -> dict[str, Any]:
        try:
            client = create_llm_client()
            fallback_used = settings.llm_provider != client.provider
            payload = {
                "configured_provider": settings.llm_provider,
                "active_provider": client.provider,
                "model_name": client.model_name,
                "fallback_used": fallback_used,
                "required": False,
            }
            if fallback_used:
                return _degraded("LLM provider 已降级到 fallback", **payload)
            return _ok("LLM provider 可用", **payload)
        except Exception as exc:
            return _degraded(
                "LLM provider 检查失败，运行时会尝试 MockLLM fallback",
                configured_provider=settings.llm_provider,
                error=str(exc),
                required=False,
            )

    def _check_event_producer(self) -> dict[str, Any]:
        producer = create_event_producer()
        producer_type = type(producer).__name__
        payload = {
            "configured_producer": settings.event_producer,
            "producer_type": producer_type,
            "required": False,
        }
        if isinstance(producer, RocketMQProducer):
            return _degraded(
                "RocketMQProducer 当前仍是 placeholder，不连接真实 NameServer",
                topic=producer.topic,
                name_server_configured=bool(producer.name_server),
                **payload,
            )
        return _ok("event producer 可用", **payload)

    def _check_trace_storage(self) -> dict[str, Any]:
        if not settings.trace_enabled:
            return _ok("trace 已关闭", enabled=False, required=False)
        try:
            storage_dir = Path(settings.trace_storage_dir)
            storage_dir.mkdir(parents=True, exist_ok=True)
            probe_path = storage_dir / ".healthcheck.tmp"
            probe_path.write_text("ok", encoding="utf-8")
            probe_path.unlink(missing_ok=True)
            return _ok("trace storage 可写", storage_dir=str(storage_dir), required=True)
        except Exception as exc:
            return _failed(
                "trace storage 不可写",
                storage_dir=settings.trace_storage_dir,
                error=str(exc),
                required=True,
            )


async def _with_timeout(awaitable: Any, timeout_seconds: float) -> Any:
    import asyncio

    return await asyncio.wait_for(awaitable, timeout=timeout_seconds)


def _ok(message: str, **extra: Any) -> dict[str, Any]:
    return {"status": "ok", "message": message, **extra}


def _degraded(message: str, **extra: Any) -> dict[str, Any]:
    return {"status": "degraded", "message": message, **extra}


def _failed(message: str, **extra: Any) -> dict[str, Any]:
    return {"status": "failed", "message": message, **extra}
