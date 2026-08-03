from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from smart_home_observer.core.models.mqtt_message import MqttMessage

T = TypeVar("T")

class MqttRepository(ABC, Generic[T]):
    @abstractmethod
    def get(self) -> T:
        """Return the current MQTT-backed state."""
