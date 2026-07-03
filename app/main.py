from fastapi import FastAPI
from time import perf_counter

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.traces import router as traces_router
from app.config import settings
from app.observability.metrics import metrics_recorder


def create_app() -> FastAPI:
    """只在入口层装配 FastAPI，业务编排交给 agent 层，避免 API 层变厚。"""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="第 11 阶段：性能优化与部署",
    )
    app.middleware("http")(_record_metrics_middleware)
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(traces_router)
    return app


async def _record_metrics_middleware(request, call_next):
    """记录本进程 HTTP 指标。

    middleware 只采集状态码和耗时，不解释业务语义；业务链路观测仍由
    observability trace 负责。
    """

    metrics_recorder.start_request()
    started = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        latency_ms = round((perf_counter() - started) * 1000, 2)
        metrics_recorder.record_request(request.method, request.url.path, status_code, latency_ms)


app = create_app()
