from collections.abc import AsyncIterator
from typing import Protocol

from topicgate.core.interfaces.observer_repo_metadata import ObserverRepoMetadata
from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.core.models.observer_model import ObserverModel


class ObserverRepository(ObserverRepoMetadata, Protocol):
    """MQTT ingestion session without application topic-state reads."""

    def get(self) -> ObserverModel: ...

    def messages(self) -> AsyncIterator[MqttMessage]: ...

    def drain_pending_messages(self) -> tuple[MqttMessage, ...]: ...
