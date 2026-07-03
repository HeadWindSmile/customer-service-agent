from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings
from app.health import HealthChecker
from app.observability.metrics import metrics_recorder


router = APIRouter(tags=["health"])
health_checker = HealthChecker()


@router.get("/health")
async def health() -> dict[str, Any]:
    """服务存活检查，只确认应用进程可响应。"""

    return await health_checker.health()


@router.get("/ready")
async def ready() -> JSONResponse:
    """依赖就绪检查。

    readiness 会区分 required 与 fallback 型依赖：Redis、LLM、事件生产者可降级，
    业务服务在显式配置后则必须可用，便于 Docker Compose healthcheck 判断。
    """

    payload = await health_checker.ready()
    return JSONResponse(payload, status_code=200 if payload["ready"] else 503)


@router.get("/metrics-lite")
async def metrics_lite() -> JSONResponse:
    """返回进程内轻量指标，避免本阶段提前接入完整 Prometheus。"""

    if not settings.metrics_lite_enabled:
        return JSONResponse({"enabled": False, "message": "metrics-lite 已关闭"}, status_code=404)
    return JSONResponse(metrics_recorder.snapshot())
