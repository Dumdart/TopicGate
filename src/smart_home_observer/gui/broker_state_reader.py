from typing import Protocol

from smart_home_observer.core.config.mqtt_config import MqttConfig


class BrokerStateReader(Protocol):
    """Provides settings for the active broker profile to the UI."""

    def get_mqtt(self) -> MqttConfig: ...

    def update_mqtt(self, mqtt: MqttConfig) -> None: ...
