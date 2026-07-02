from fastapi import APIRouter

from app.agents.customer_agent import CustomerAgent
from app.schemas.chat import ChatRequest, ChatResponse


router = APIRouter(prefix="/api", tags=["chat"])
agent = CustomerAgent()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """API 层保持薄封装，核心流程统一交给 CustomerAgent 编排。"""
    return await agent.handle(request)
