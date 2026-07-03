from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.events.event_type import EventType


class Event(BaseModel):
    """统一业务事件模型。

    第 9 阶段只定义生产侧事件契约，不提前引入消费端、重试表或数据库；所有事件都带
    trace_id，方便后续第 10 阶段继续做 trace 关联和问题复盘。
    """

    model_config = ConfigDict(use_enum_values=True)

    event_id: str = Field(default_factory=lambda: uuid4().hex)
    event_type: EventType
    trace_id: str
    user_id: str
    session_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
