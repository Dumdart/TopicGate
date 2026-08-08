from datetime import datetime, timezone

from topicgate.core.config.app_config import AppConfig
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.observer_model import TopicState
from topicgate.core.models.subscription import Subscription
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.repository.broker_repository import BrokerRepository
from topicgate.services.observer_model_service import ObserverModelService


def test_broker_repository_persists_profiles_and_rebuilds_workspace_tree() -> None:
    database = DatabaseContext("sqlite:///:memory:")
    settings = AppConfig(MqttConfig("default", 1883, "user", "secret"))
    repository = BrokerRepository(database, settings)
    profile = repository.create_profile(
        "Remote",
        MqttConfig("remote", 8883, "observer", "secret", use_tls=True),
    )
    profile.workspace.subscriptions = (
        Subscription("home/+/status", qos=2),
        Subscription("home/#"),
    )
    profile.workspace.model.topic_states["runtime/value"] = TopicState(
        name="value",
        topic="runtime/value",
        payload=b"42",
        qos=1,
        retain=False,
        recieved_at=datetime.now(timezone.utc),
    )
    repository.update_profile(profile)
    repository.activate_profile(profile.id)

    reloaded = BrokerRepository(database)
    persisted = reloaded.get_profile(profile.id)

    assert reloaded.get_profile().id == profile.id
    assert persisted.name == "Remote"
    assert persisted.config == MqttConfig(
        "remote",
        8883,
        "observer",
        "",
        use_tls=True,
        id=persisted.config.id,
    )
    assert persisted.workspace.subscriptions == profile.workspace.subscriptions
    assert ObserverModelService.get_all_topics(persisted.workspace.model) == [
        "home/+/status",
        "home/#",
    ]
    assert persisted.workspace.model.topic_states == {}
    database.dispose()


def test_broker_repository_reads_changes_made_by_another_instance() -> None:
    database = DatabaseContext("sqlite:///:memory:")
    settings = AppConfig(MqttConfig("default", 1883, "user", "secret"))
    first = BrokerRepository(database, settings)
    second = BrokerRepository(database)

    profile = first.create_profile(
        "Remote",
        MqttConfig("remote", 8883, "observer", "secret", use_tls=True),
    )
    profile.workspace.subscriptions = (Subscription("home/#", qos=2),)
    first.update_profile(profile)
    first.activate_profile(profile.id)

    persisted = second.get_profile(profile.id)
    assert second.get_profile().id == profile.id
    assert persisted.name == "Remote"
    assert persisted.workspace.subscriptions == (Subscription("home/#", qos=2),)

    persisted.name = "Not persisted"
    assert second.get_profile(profile.id).name == "Remote"
    database.dispose()


def test_broker_repository_hydrates_the_active_password_from_runtime_settings() -> None:
    database = DatabaseContext("sqlite:///:memory:")
    persisted_settings = AppConfig(
        MqttConfig("broker", 1883, "observer", "initial-secret")
    )
    BrokerRepository(database, persisted_settings)
    runtime_settings = AppConfig(
        MqttConfig("ignored-host", 9999, "ignored-user", "runtime-secret")
    )

    reloaded = BrokerRepository(database, runtime_settings)

    config = reloaded.get_mqtt()
    assert config.host == "broker"
    assert config.port == 1883
    assert config.username == "observer"
    assert config.password == "runtime-secret"
    database.dispose()
