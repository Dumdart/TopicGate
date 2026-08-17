from unittest.mock import MagicMock

from topicgate.core.config.app_config import AppConfig
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.observer_model import ObserverModel
from topicgate.app.services.broker_profile_service import BrokerProfileService

def test_broker_repository_returns_initial_settings(credential_store) -> None:
    config = AppConfig(
        mqtt=MqttConfig("broker", 1883, "observer", "password")
    )

    repository = BrokerProfileService(config, credential_store=credential_store)

    assert repository.get() is config
    assert repository.get_mqtt() == config.mqtt


def test_broker_repository_uses_local_defaults_without_configuration_file(
    credential_store,
) -> None:
    repository = BrokerProfileService(credential_store=credential_store)

    assert repository.get_mqtt() == MqttConfig("localhost", 1883, "", "")


def test_broker_repository_updates_complete_settings_and_saves(
    credential_store,
) -> None:
    repository = BrokerProfileService(
        AppConfig(MqttConfig("old", 1883, "", "")),
        credential_store=credential_store,
    )
    repository.save = MagicMock()
    replacement = AppConfig(MqttConfig("new", 8883, "observer", "password", True))

    repository.update(replacement)

    assert repository.get() is replacement
    repository.save.assert_called_once_with()


def test_broker_repository_updates_mqtt_settings_and_saves(
    credential_store,
) -> None:
    initial = AppConfig(MqttConfig("old", 1883, "", ""))
    repository = BrokerProfileService(initial, credential_store=credential_store)
    repository.save = MagicMock()
    replacement = MqttConfig("new", 8883, "observer", "password", True)

    repository.update_mqtt(replacement)

    assert repository.get_mqtt() == replacement
    assert repository.get().mqtt == replacement
    repository.save.assert_called_once_with()


def test_broker_repository_links_observer_model_to_active_profile(
    credential_store,
) -> None:
    repository = BrokerProfileService(
        AppConfig(MqttConfig("broker", 1883, "", "")),
        credential_store=credential_store,
    )
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


def test_broker_repository_provides_two_empty_independent_profiles(
    credential_store,
) -> None:
    repository = BrokerProfileService(
        AppConfig(MqttConfig("broker", 1883, "", "")),
        credential_store=credential_store,
    )

    default_profile, local_profile = repository.get_all_profiles()

    assert [profile.name for profile in (default_profile, local_profile)] == [
        "Default",
        "Local MQTT",
    ]
    assert local_profile.config == MqttConfig("localhost", 1883, "", "")
    assert default_profile.workspace.model is not local_profile.workspace.model
    assert default_profile.workspace.subscriptions == ()
    assert local_profile.workspace.subscriptions == ()


def test_broker_repository_creates_updates_and_deletes_profiles(
    credential_store,
) -> None:
    repository = BrokerProfileService(
        AppConfig(MqttConfig("broker", 1883, "", "")),
        credential_store=credential_store,
    )
    repository.save = MagicMock()

    profile = repository.create_profile(
        "  Remote  ",
        MqttConfig("remote", 8883, "user", "secret", True),
    )

    assert profile.name == "Remote"
    assert profile.workspace.profile_id == profile.id
    assert profile.workspace.model == ObserverModel(root_stats=[])
    assert profile.workspace.subscriptions == ()
    assert credential_store.get_password(profile.id) == "secret"

    profile.name = "Remote TLS"
    profile.config = MqttConfig("remote-new", 8883, "user", "new-secret", True)
    repository.update_profile(profile)

    assert repository.get_profile(profile.id).name == "Remote TLS"
    assert credential_store.get_password(profile.id) == "new-secret"
    deleted = repository.delete_profile(profile.id)
    assert deleted is profile
    assert profile not in repository.get_all_profiles()
    assert credential_store.get_password(profile.id) is None
    assert repository.save.call_count == 3


def test_broker_profile_service_rejects_duplicate_names(
    credential_store,
) -> None:
    repository = BrokerProfileService(
        AppConfig(MqttConfig("broker", 1883, "", "")),
        credential_store=credential_store,
    )
    try:
        repository.create_profile(" default ", MqttConfig("other", 1883, "", ""))
    except ValueError as error:
        assert str(error) == "A broker profile with that name already exists."
    else:
        raise AssertionError("Expected a duplicate profile name to be rejected")



def test_broker_repository_allows_plaintext_credential_mutations(
    credential_store,
) -> None:
    repository = BrokerProfileService(credential_store=credential_store)
    active_profile = repository.get_profile()
    insecure = MqttConfig("broker", 1883, "observer", "secret")

    created = repository.create_profile("Plain MQTT", insecure)
    repository.activate_profile(active_profile.id, insecure)
    active_profile.config = insecure
    repository.update_profile(active_profile)

    assert created.config == insecure
    assert len(repository.get_all_profiles()) == 3
    assert repository.get_mqtt() == insecure
