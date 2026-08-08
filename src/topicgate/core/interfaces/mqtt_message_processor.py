from abc import ABC, abstractmethod
from typing import TypeVar, Generic

from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.core.models.mqtt_state import MqttState

T = TypeVar("T", bound=MqttState)

class MqttMessageProcessor(ABC, Generic[T]):
    @abstractmethod
    def process(self, state: T, message: MqttMessage) -> None:
        """Apply one MQTT message to the current state."""
