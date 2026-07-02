from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="当前调用方用户 ID")
    session_id: str = Field(..., min_length=1, description="会话 ID")
    role: Literal["user", "agent"] = Field(..., description="调用方角色")
    message: str = Field(..., min_length=1, description="用户输入")
    target_user_id: str | None = Field(
        default=None,
        description="客服代查时的目标用户；普通用户不应查询他人信息",
    )


class Source(BaseModel):
    doc_id: str
    title: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    tool_name: str
    input: dict[str, Any]
    output: dict[str, Any]
    success: bool
    latency_ms: float
    error_message: str | None = None


class IntentResult(BaseModel):
    intent: str
    slots: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class ChatResponse(BaseModel):
    answer: str
    intent: str
    slots: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    intent_reason: str = ""
    sources: list[Source]
    tool_calls: list[ToolCall]
    trace_id: str
    latency_ms: float
    error: str | None = None
    rewritten_query: str | None = None
