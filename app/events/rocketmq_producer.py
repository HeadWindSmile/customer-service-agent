from app.config import settings
from app.events.event_schema import Event
from app.events.producer import BaseEventProducer
from app.observability.logger import log_event


class RocketMQProducer(BaseEventProducer):
    """RocketMQ 生产者占位实现。

    当前阶段只保留 topic、tag、message_key、payload 的结构，刻意不引入真实 SDK 和
    NameServer 连接，避免本地 demo 因外部 MQ 不可用而无法启动。
    """

    def __init__(self, name_server: str | None = None, topic: str | None = None) -> None:
        self.name_server = name_server or settings.rocketmq_name_server
        self.topic = topic or settings.rocketmq_topic

    async def send(self, event: Event) -> bool:
        message = {
            "name_server": self.name_server,
            "topic": self.topic,
            "tag": event.event_type,
            "message_key": event.event_id,
            "payload": event.to_json_dict(),
        }
        log_event(
            "event.rocketmq_placeholder",
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "trace_id": event.trace_id,
                "topic": self.topic,
                "tag": event.event_type,
                "message_key": event.event_id,
                "rocketmq_configured": bool(self.name_server),
                "placeholder_payload_keys": sorted(message["payload"].keys()),
            },
        )
        return True
