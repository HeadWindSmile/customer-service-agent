from enum import Enum


class EventType(str, Enum):
    """统一事件类型。

    事件名使用业务语义而不是 producer 语义，避免上层代码关心消息队列的 topic、
    tag 或 SDK 细节，后续从 mock 切换到 RocketMQ 时事件契约保持稳定。
    """

    TICKET_CREATED = "TICKET_CREATED"
    AUDIT_LOG_CREATED = "AUDIT_LOG_CREATED"
    AI_QA_FINISHED = "AI_QA_FINISHED"
    SAFETY_REVIEW_REQUIRED = "SAFETY_REVIEW_REQUIRED"
    USER_FEEDBACK_CREATED = "USER_FEEDBACK_CREATED"
