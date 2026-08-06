from unittest.mock import MagicMock

from smart_home_observer.core.config.app_config import AppConfig
from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.observer_model import ObserverModel
from smart_home_observer.infrastructure.repository.broker_repository import (
    BrokerRepository,
)


def test_broker_repository_returns_initial_settings() -> None:
    config = AppConfig(
        mqtt=MqttConfig("broker", 1883, "observer", "password")
    )

    repository = BrokerRepository(config)

    assert repository.get() is config
    assert repository.get_mqtt() == config.mqtt


def test_broker_repository_updates_complete_settings_and_saves() -> None:
    repository = BrokerRepository(AppConfig(MqttConfig("old", 1883, "", "")))
    repository.save = MagicMock()
    replacement = AppConfig(MqttConfig("new", 8883, "observer", "password", True))

    repository.update(replacement)

    assert repository.get() is replacement
    repository.save.assert_called_once_with()


def test_broker_repository_updates_mqtt_settings_and_saves() -> None:
    initial = AppConfig(MqttConfig("old", 1883, "", ""))
    repository = BrokerRepository(initial)
    repository.save = MagicMock()
    replacement = MqttConfig("new", 8883, "observer", "password", True)

    repository.update_mqtt(replacement)

    assert repository.get_mqtt() == replacement
    assert repository.get().mqtt == replacement
    repository.save.assert_called_once_with()


def test_broker_repository_links_observer_model_to_active_profile() -> None:
    repository = BrokerRepository(AppConfig(MqttConfig("broker", 1883, "", "")))
    replacement = ObserverModel(root_stats=[])
    repository.save = MagicMock()

    repository.update_observer_model(replacement)

    profile = repository.get_profile()
    workspace = repository.get_observer_workspace()
    assert repository.get_observer_model() is replacement
    assert workspace.model is replacement
    assert workspace.profile_id == profile.id
    assert profile.workspace_id == workspace.id
    repository.save.assert_called_once_with()


def test_broker_repository_provides_two_independent_profiles() -> None:
    repository = BrokerRepository(AppConfig(MqttConfig("broker", 1883, "", "")))

    default_profile, local_profile = repository.get_all_profiles()

    assert [profile.name for profile in (default_profile, local_profile)] == [
        "Default",
        "Local MQTT",
    ]
    assert local_profile.config == MqttConfig("localhost", 1883, "", "")
    assert default_profile.workspace.model is not local_profile.workspace.model
