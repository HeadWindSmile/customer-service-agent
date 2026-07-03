from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.traces import router as traces_router
from app.config import settings


def create_app() -> FastAPI:
    """只在入口层装配 FastAPI，业务编排交给 agent 层，避免 API 层变厚。"""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="第 10 阶段：可观测性与 AI 效果评测体系",
    )
    app.include_router(chat_router)
    app.include_router(traces_router)
    return app


app = create_app()
