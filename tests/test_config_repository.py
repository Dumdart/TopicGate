from unittest.mock import MagicMock

from smart_home_observer.core.config.app_config import AppConfig
from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.infrastructure.repository.config_repository import (
    ConfigRepository,
)


def test_config_repository_returns_initial_settings() -> None:
    config = AppConfig(
        mqtt=MqttConfig("broker", 1883, "observer", "password")
    )

    repository = ConfigRepository(config)

    assert repository.get() is config
    assert repository.get_mqtt() == config.mqtt


def test_config_repository_updates_complete_settings_and_saves() -> None:
    repository = ConfigRepository(AppConfig(MqttConfig("old", 1883, "", "")))
    repository.save = MagicMock()
    replacement = AppConfig(MqttConfig("new", 8883, "observer", "password", True))

    repository.update(replacement)

    assert repository.get() is replacement
    repository.save.assert_called_once_with()


def test_config_repository_updates_mqtt_settings_and_saves() -> None:
    initial = AppConfig(MqttConfig("old", 1883, "", ""))
    repository = ConfigRepository(initial)
    repository.save = MagicMock()
    replacement = MqttConfig("new", 8883, "observer", "password", True)

    repository.update_mqtt(replacement)

    assert repository.get_mqtt() == replacement
    assert repository.get().mqtt == replacement
    repository.save.assert_called_once_with()
