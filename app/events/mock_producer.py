import json
import os

from app.config import settings
from app.events.event_schema import Event
from app.events.producer import BaseEventProducer
from app.observability.logger import log_event


class MockEventProducer(BaseEventProducer):
    """本地事件生产者。

    写 JSON Lines 而不是接真实 MQ，是为了让第 9 阶段在无 RocketMQ、无数据库的环境
    下也能完整演示事件生产链路，并且方便 pytest 直接验证事件内容。
    """

    def __init__(self, log_path: str | None = None) -> None:
        self.log_path = log_path or settings.event_log_path

    async def send(self, event: Event) -> bool:
        parent = os.path.dirname(self.log_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as file:
            file.write(json.dumps(event.to_json_dict(), ensure_ascii=False, default=str) + "\n")
        log_event(
            "event.mock_published",
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "trace_id": event.trace_id,
            },
        )
        return True
