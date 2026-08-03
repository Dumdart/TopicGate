from abc import abstractmethod
from typing import Generic, TypeVar

from smart_home_observer.app.service_item import ServiceItem

T = TypeVar("T")

class MqttRepository(ServiceItem, Generic[T]):
    @abstractmethod
    def get(self) -> T:
        """Return the current MQTT-backed state."""
