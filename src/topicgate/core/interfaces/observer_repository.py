from collections.abc import AsyncIterator
from datetime import datetime
from typing import Protocol

from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.core.models.mqtt_observation import MqttObservation
from topicgate.core.models.observer_model import ObserverModel
from topicgate.core.models.subscription import Subscription


class ObserverRepository(Protocol):
    """Application-facing access to an MQTT observer."""

    @property
    def connection_status(self) -> object: ...

    @property
    def topic_update_interval(self) -> float: ...

    @property
    def dropped_message_count(self) -> int: ...

    @property
    def connected_at(self) -> datetime | None: ...

    @property
    def observation_started_at(self) -> datetime | None: ...

    @property
    def subscriptions(self) -> tuple[Subscription, ...]: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    def get(self) -> ObserverModel: ...

    def get_state(self, topic: str, /) -> MqttObservation | None: ...

    def get_all_topics(self) -> tuple[str, ...]: ...

    def messages(self) -> AsyncIterator[MqttMessage]: ...

    def drain_pending_messages(self) -> tuple[MqttMessage, ...]: ...

    def connection_statuses(self) -> AsyncIterator[object]: ...

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def reconnect(self) -> None: ...

    async def update_broker(
        self,
        new_config: MqttConfig,
        /,
        model: ObserverModel | None = None,
        subscriptions: tuple[Subscription, ...] | None = None,
    ) -> None: ...

    async def add_subscription(self, subscription: Subscription, /) -> None: ...

    async def update_subscription(
        self,
        original_filter: str,
        subscription: Subscription,
        /,
    ) -> None: ...

    async def remove_subscription(self, subscription: Subscription, /) -> None: ...

    async def publish(self, topic: str, payload: bytes, /) -> None: ...
