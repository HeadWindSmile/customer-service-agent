from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.observability.metrics import metrics_recorder


router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics() -> PlainTextResponse:
    """Prometheus-compatible 文本指标。

    API 层只负责暴露文本格式；指标采集和聚合仍集中在 observability 层，便于
    后续替换为正式 Prometheus/OTel SDK。
    """

    if not settings.metrics_lite_enabled:
        return PlainTextResponse("metrics disabled\n", status_code=404)
    return PlainTextResponse(
        metrics_recorder.prometheus_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
