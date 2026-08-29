from datetime import datetime, timezone
from uuid import uuid4

from topicgate.core.config.app_config import AppConfig
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.topic_message import TopicMessage
from topicgate.core.models.subscription import Subscription
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.app.services.broker_profile_service import BrokerProfileService
from topicgate.infrastructure.repository.topic_message_repository import (
    TopicMessageRepository,
)


def test_broker_repository_persists_profiles_and_workspace_subscriptions(
    credential_store,
) -> None:
    database = DatabaseContext("sqlite:///:memory:")
    settings = AppConfig(MqttConfig("default", 1883, "user", "secret"))
    repository = BrokerProfileService(
        database, settings, credential_store=credential_store
    )
    profile = repository.create_profile(
        "Remote",
        MqttConfig("remote", 8883, "observer", "secret", use_tls=True),
    )
    profile.workspace.subscriptions = (
        Subscription("home/+/status", qos=2),
        Subscription("home/#"),
    )
    repository.update_profile(profile)
    repository.activate_profile(profile.id)

    reloaded = BrokerProfileService(database, credential_store=credential_store)
    persisted = reloaded.get_profile(profile.id)

    assert reloaded.get_profile().id == profile.id
    assert persisted.name == "Remote"
    assert persisted.config == MqttConfig(
        "remote",
        8883,
        "observer",
        "secret",
        use_tls=True,
        id=persisted.config.id,
    )
    assert persisted.workspace.subscriptions == profile.workspace.subscriptions
    database.dispose()


def test_broker_repository_reads_changes_made_by_another_instance(
    credential_store,
) -> None:
    database = DatabaseContext("sqlite:///:memory:")
    settings = AppConfig(MqttConfig("default", 1883, "user", "secret"))
    first = BrokerProfileService(database, settings, credential_store=credential_store)
    second = BrokerProfileService(database, credential_store=credential_store)

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


def test_broker_repository_prefers_a_stored_password_to_supplied_settings(
    credential_store,
) -> None:
    database = DatabaseContext("sqlite:///:memory:")
    persisted_settings = AppConfig(
        MqttConfig("broker", 1883, "observer", "initial-secret")
    )
    BrokerProfileService(
        database, persisted_settings, credential_store=credential_store
    )
    runtime_settings = AppConfig(
        MqttConfig("ignored-host", 9999, "ignored-user", "runtime-secret")
    )

    reloaded = BrokerProfileService(
        database, runtime_settings, credential_store=credential_store
    )

    config = reloaded.get_mqtt()
    assert config.host == "broker"
    assert config.port == 1883
    assert config.username == "observer"
    assert config.password == "initial-secret"
    database.dispose()


def test_broker_repository_imports_a_supplied_password_when_store_is_empty(
    credential_store,
) -> None:
    database = DatabaseContext("sqlite:///:memory:")
    BrokerProfileService(
        database,
        AppConfig(MqttConfig("broker", 1883, "observer", "")),
        credential_store=credential_store,
    )
    runtime_settings = AppConfig(
        MqttConfig("ignored-host", 9999, "ignored-user", "runtime-secret")
    )

    reloaded = BrokerProfileService(
        database,
        runtime_settings,
        credential_store=credential_store,
    )

    profile = reloaded.get_profile()
    assert profile.config.password == "runtime-secret"
    assert credential_store.get_password(profile.id) == "runtime-secret"
    database.dispose()


def test_deleting_broker_cascades_to_persisted_topic_messages(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'broker-cascade.db'}")
    profiles = BrokerProfileService(database, credential_store=credential_store)
    profile = profiles.get_profile()
    messages = TopicMessageRepository(database)
    profiles = BrokerProfileService(
        database,
        credential_store=credential_store,
        topic_messages=messages,
    )
    message = TopicMessage(
        broker_id=profile.id,
        topic="factory/temperature",
        payload=b"21.5",
        qos=1,
        retain=True,
        received_at=datetime.now(timezone.utc),
        payload_size=4,
        message_count=1,
        observation_id=uuid4(),
    )

    try:
        messages.update_message(message)
        messages.flush()

        profiles.delete_profile(profile.id)

        assert messages.get_current_topics(profile.id) == ()
    finally:
        messages.close()
        database.dispose()
