from abc import ABC, abstractmethod

from app.events.event_schema import Event


class BaseEventProducer(ABC):
    """事件生产者抽象。

    主链路只依赖这个接口，避免 CustomerAgent、Router 或 tools 直接绑定某个 MQ SDK。
    本地默认实现是 JSON Lines，生产环境可以替换为 RocketMQProducer。
    """

    @abstractmethod
    async def send(self, event: Event) -> bool:
        raise NotImplementedError


class NoneEventProducer(BaseEventProducer):
    """显式关闭事件发送时使用。

    保留 none 模式是为了便于本地排查问题或在测试中隔离事件副作用。
    """

    async def send(self, event: Event) -> bool:
        return True
