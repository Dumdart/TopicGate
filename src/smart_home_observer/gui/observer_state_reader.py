from collections.abc import AsyncIterator
from typing import Protocol

from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.observer_model import ObserverModel, TopicState
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.core.config.mqtt_config import MqttConfig


class ObserverStateReader(Protocol):
    """Provides observer state and runtime subscription operations to the UI."""

    connection_status: object

    def get(self) -> ObserverModel: ...

    def get_state(self, topic: str) -> TopicState | None: ...

    def messages(self) -> AsyncIterator[MqttMessage]: ...

    def connection_statuses(self) -> AsyncIterator[object]: ...

    async def add_subscription(self, subscription: Subscription) -> None: ...

    async def update_subscription(
        self, original_filter: str, subscription: Subscription
    ) -> None: ...

    async def remove_subscription(self, subscription: Subscription) -> None: ...

    async def reconnect(self) -> None: ...

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def update_broker(self, new_config: MqttConfig) -> None: ...
