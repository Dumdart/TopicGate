from collections.abc import AsyncIterator
from typing import Protocol

from topicgate.core.interfaces.observer_repo_metadata import ObserverRepoMetadata
from topicgate.core.models.mqtt_message import MqttMessage


class ObserverRepository(ObserverRepoMetadata, Protocol):
    """MQTT ingestion session without application topic-state reads."""

    def messages(self) -> AsyncIterator[MqttMessage]: ...

    def drain_pending_messages(self) -> tuple[MqttMessage, ...]: ...
