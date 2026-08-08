from abc import abstractmethod
from typing import Generic, TypeVar

from topicgate.app.service_item import ServiceItem
from topicgate.core.models.observer_model import TopicState

T = TypeVar("T")

class MqttRepository(ServiceItem, Generic[T]):
    @abstractmethod
    def get(self) -> T:
        """Return the current MQTT-backed state."""
    @abstractmethod
    def get_value(self, topic: str) -> bytes | None:
        """REturn the value of a topic."""
    @abstractmethod
    def get_state(self, topic: str) -> TopicState | None:
        """Return the state of a topic."""
