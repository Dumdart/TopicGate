from abc import abstractmethod
from typing import Generic, TypeVar

from smart_home_observer.app.service_item import ServiceItem
from smart_home_observer.core.models.observer_model import TopicState

T = TypeVar("T")

class MqttRepository(ServiceItem, Generic[T]):
    @abstractmethod
    def get(self) -> T:
        """Return the current MQTT-backed state."""
    @abstractmethod
    def get_value(self, topic) -> bytes | None:
        """REturn the value of a topic."""
    @abstractmethod
    def get_state(self, topic) -> TopicState | None:
        """Return the state of a topic."""
