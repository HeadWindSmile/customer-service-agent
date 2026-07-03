from typing import Any

from app.config import settings
from app.events.event_schema import Event
from app.events.event_type import EventType
from app.events.mock_producer import MockEventProducer
from app.events.producer import BaseEventProducer, NoneEventProducer
from app.events.rocketmq_producer import RocketMQProducer
from app.observability.logger import log_event


class EventBus:
    """事件总线门面。

    CustomerAgent 通过 EventBus 发布业务事件，EventBus 负责选择 producer、统一建模
    和失败隔离。这样 MQ 失败只会进入 warning 日志，不会破坏 /api/chat 主链路。
    """

    def __init__(self, producer: BaseEventProducer | None = None) -> None:
        self.producer = producer or create_event_producer()

    async def publish(
        self,
        *,
        event_type: EventType,
        trace_id: str,
        user_id: str,
        session_id: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        event = Event(
            event_type=event_type,
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
            payload=payload or {},
        )
        try:
            sent = await self.producer.send(event)
        except Exception as exc:
            log_event(
                "event.publish_failed",
                {
                    "event_type": event_type.value,
                    "trace_id": trace_id,
                    "error": str(exc),
                },
                level="warning",
            )
            return False
        if not sent:
            log_event(
                "event.publish_failed",
                {
                    "event_type": event_type.value,
                    "trace_id": trace_id,
                    "error": "producer returned false",
                },
                level="warning",
            )
        return sent

    async def publish_ticket_created(self, *, trace_id: str, user_id: str, session_id: str, payload: dict[str, Any]) -> bool:
        return await self.publish(
            event_type=EventType.TICKET_CREATED,
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
            payload=payload,
        )

    async def publish_audit_log_created(self, *, trace_id: str, user_id: str, session_id: str, payload: dict[str, Any]) -> bool:
        return await self.publish(
            event_type=EventType.AUDIT_LOG_CREATED,
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
            payload=payload,
        )

    async def publish_ai_qa_finished(self, *, trace_id: str, user_id: str, session_id: str, payload: dict[str, Any]) -> bool:
        return await self.publish(
            event_type=EventType.AI_QA_FINISHED,
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
            payload=payload,
        )

    async def publish_safety_review_required(
        self,
        *,
        trace_id: str,
        user_id: str,
        session_id: str,
        payload: dict[str, Any],
    ) -> bool:
        return await self.publish(
            event_type=EventType.SAFETY_REVIEW_REQUIRED,
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
            payload=payload,
        )

    async def publish_user_feedback_created(
        self,
        *,
        trace_id: str,
        user_id: str,
        session_id: str,
        payload: dict[str, Any],
    ) -> bool:
        return await self.publish(
            event_type=EventType.USER_FEEDBACK_CREATED,
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
            payload=payload,
        )


def create_event_producer() -> BaseEventProducer:
    producer_name = settings.event_producer
    if producer_name == "none":
        return NoneEventProducer()
    if producer_name == "rocketmq":
        return RocketMQProducer()
    if producer_name != "mock":
        log_event(
            "event.producer_unknown",
            {"configured": producer_name, "fallback": "mock"},
            level="warning",
        )
    return MockEventProducer()
