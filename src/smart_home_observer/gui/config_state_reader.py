from typing import Protocol

from smart_home_observer.core.config.app_config import AppConfig
from smart_home_observer.core.config.mqtt_config import MqttConfig


class ConfigStateReader(Protocol):
    """Provides application configuration to the UI."""

    def get(self) -> AppConfig: ...

    def get_mqtt(self) -> MqttConfig: ...

    def update_mqtt(self, mqtt: MqttConfig) -> None: ...
