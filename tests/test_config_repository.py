from unittest.mock import MagicMock

from smart_home_observer.core.config.app_config import AppConfig
from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.observer_model import ObserverModel
from smart_home_observer.infrastructure.database.database_context import DatabaseContext
from smart_home_observer.infrastructure.repository.config_repository import (
    ConfigRepository,
)
from smart_home_observer.infrastructure.repository.broker_repository import (
    BrokerRepository,
)


def test_config_repository_updates_the_linked_mqtt_configuration() -> None:
    database = DatabaseContext("sqlite:///:memory:")
    repository = ConfigRepository(database)
    original = repository.create_app_config(
        AppConfig(MqttConfig("old-broker", 1883, "old-user", "password")),
    )

    replacement = AppConfig(
        id=original.id,
        mqtt=MqttConfig(
            "new-broker",
            8883,
            "new-user",
            "password",
            use_tls=True,
            id=original.mqtt.id,
        ),
    )

    repository.update_app_config(replacement)
    persisted = ConfigRepository(database).get_app_config(replacement.id)

    assert persisted is not None
    assert persisted.id == replacement.id
    assert persisted.mqtt.host == replacement.mqtt.host
    assert persisted.mqtt.port == replacement.mqtt.port
    assert persisted.mqtt.username == replacement.mqtt.username
    assert persisted.mqtt.use_tls == replacement.mqtt.use_tls
    assert persisted.mqtt.id == replacement.mqtt.id
    assert repository.is_updated
    database.dispose()


def test_config_repository_reads_each_configuration_from_the_database() -> None:
    database = DatabaseContext("sqlite:///:memory:")
    repository = ConfigRepository(database)
    first = repository.create_app_config(
        AppConfig(MqttConfig("first", 1883, "one", "password"))
    )
    second = repository.create_app_config(
        AppConfig(MqttConfig("second", 8883, "two", "password", use_tls=True))
    )

    assert repository.get_all_app_configs() == [
        AppConfig(
            id=first.id,
            mqtt=MqttConfig("first", 1883, "one", "", id=first.mqtt.id),
        ),
        AppConfig(
            id=second.id,
            mqtt=MqttConfig(
                "second",
                8883,
                "two",
                "",
                use_tls=True,
                id=second.mqtt.id,
            ),
        ),
    ]
    database.dispose()


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


def test_broker_repository_provides_two_empty_independent_profiles() -> None:
    repository = BrokerRepository(AppConfig(MqttConfig("broker", 1883, "", "")))

    default_profile, local_profile = repository.get_all_profiles()

    assert [profile.name for profile in (default_profile, local_profile)] == [
        "Default",
        "Local MQTT",
    ]
    assert local_profile.config == MqttConfig("localhost", 1883, "", "")
    assert default_profile.workspace.model is not local_profile.workspace.model
    assert default_profile.workspace.subscriptions == ()
    assert local_profile.workspace.subscriptions == ()


def test_broker_repository_creates_updates_and_deletes_profiles() -> None:
    repository = BrokerRepository(AppConfig(MqttConfig("broker", 1883, "", "")))
    repository.save = MagicMock()

    profile = repository.create_profile(
        "  Remote  ",
        MqttConfig("remote", 8883, "user", "secret", True),
    )

    assert profile.name == "Remote"
    assert profile.workspace.profile_id == profile.id
    assert profile.workspace.model == ObserverModel(root_stats=[])
    assert profile.workspace.subscriptions == ()

    profile.name = "Remote TLS"
    profile.config = MqttConfig("remote-new", 8883, "user", "secret", True)
    repository.update_profile(profile)

    assert repository.get_profile(profile.id).name == "Remote TLS"
    deleted = repository.delete_profile(profile.id)
    assert deleted is profile
    assert profile not in repository.get_all_profiles()
    assert repository.save.call_count == 3


def test_broker_repository_rejects_duplicate_names_and_active_deletion() -> None:
    repository = BrokerRepository(AppConfig(MqttConfig("broker", 1883, "", "")))
    active_profile = repository.get_profile()

    try:
        repository.create_profile(" default ", MqttConfig("other", 1883, "", ""))
    except ValueError as error:
        assert str(error) == "A broker profile with that name already exists."
    else:
        raise AssertionError("Expected a duplicate profile name to be rejected")

    try:
        repository.delete_profile(active_profile.id)
    except ValueError as error:
        assert str(error) == "The active broker profile cannot be deleted."
    else:
        raise AssertionError("Expected active profile deletion to be rejected")
