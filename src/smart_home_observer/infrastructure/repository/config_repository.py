from smart_home_observer.core.config.app_config import AppConfig
from smart_home_observer.core.config.config_loader import ConfigLoader
from smart_home_observer.core.config.mqtt_config import MqttConfig


class ConfigRepository:
    """In-memory application configuration until persistent settings are added."""

    def __init__(self, settings: AppConfig | None = None) -> None:
        self._settings = settings or ConfigLoader().load_config()

    def get(self) -> AppConfig:
        return self._settings

    def get_mqtt(self) -> MqttConfig:
        return self._settings.mqtt

    def update(self, settings: AppConfig) -> None:
        self._settings = settings
        self.save()

    def update_mqtt(self, mqtt: MqttConfig) -> None:
        self._settings.mqtt = mqtt
        self.save()

    def save(self) -> None:
        """Persist settings when a durable repository is introduced."""
