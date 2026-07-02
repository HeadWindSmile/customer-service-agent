from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.config import settings


def create_app() -> FastAPI:
    """只在入口层装配 FastAPI，业务编排交给 agent 层，避免 API 层变厚。"""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="第 5 阶段：业务工具调用与 Spring Boot 边界",
    )
    app.include_router(chat_router)
    return app


app = create_app()
