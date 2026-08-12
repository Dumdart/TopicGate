import pytest

from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.subscription import Subscription
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.repository.subscription_repository import (
    SubscriptionRepository,
)
from topicgate.infrastructure.repository.broker_repository import BrokerRepository
from topicgate.infrastructure.repository.broker_config_repository import (
    BrokerConfigRepository,
)


def create_workspace(database: DatabaseContext):
    config_id = BrokerConfigRepository(database).create(
        MqttConfig("broker", 1883, "", "")
    )
    return BrokerRepository(database).create_profile("Default", config_id).workspace_id


def test_subscription_repository_supports_the_full_crud_lifecycle() -> None:
    database = DatabaseContext("sqlite:///:memory:")
    repository = SubscriptionRepository(database)
    workspace_id = create_workspace(database)
    original = Subscription("SmartHome/door/#", qos=1)
    replacement = Subscription(
        "SmartHome/door/status",
        qos=2,
        retain_as_published=True,
        retain_handling=1,
    )

    assert repository.add(workspace_id, original) == original
    assert repository.list_for_workspace(workspace_id) == (original,)

    assert repository.update(workspace_id, original.topic_filter, replacement) == replacement
    assert repository.list_for_workspace(workspace_id) == (replacement,)

    assert repository.remove(workspace_id, replacement.topic_filter) == replacement
    assert repository.list_for_workspace(workspace_id) == ()
    database.dispose()


def test_subscription_repository_rejects_duplicate_topic_filters() -> None:
    database = DatabaseContext("sqlite:///:memory:")
    repository = SubscriptionRepository(database)
    workspace_id = create_workspace(database)
    subscription = Subscription("SmartHome/door/#")
    repository.add(workspace_id, subscription)

    with pytest.raises(ValueError, match="already exists"):
        repository.add(workspace_id, subscription)

    database.dispose()
