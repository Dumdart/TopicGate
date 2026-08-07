from datetime import datetime, timezone

from smart_home_observer.core.config.app_config import AppConfig
from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.observer_model import TopicState
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.infrastructure.database.database_context import DatabaseContext
from smart_home_observer.infrastructure.repository.broker_repository import BrokerRepository
from smart_home_observer.services.observer_model_service import ObserverModelService


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
