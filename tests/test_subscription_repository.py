import pytest

from topicgate.core.models.subscription import Subscription
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.repository.subscription_repository import (
    SubscriptionRepository,
)


def test_subscription_repository_supports_the_full_crud_lifecycle() -> None:
    database = DatabaseContext("sqlite:///:memory:")
    repository = SubscriptionRepository(database)
    original = Subscription("SmartHome/door/#", qos=1)
    replacement = Subscription(
        "SmartHome/door/status",
        qos=2,
        retain_as_published=True,
        retain_handling=1,
    )

    assert repository.create_subscription(original) == original
    assert repository.get_subscription_by_topic(original.topic_filter) == original
    assert repository.get_all_subscriptions() == [original]

    assert repository.update_subscription(original.topic_filter, replacement) == replacement
    assert repository.get_subscription_by_topic(original.topic_filter) is None
    assert repository.get_subscription_by_topic(replacement.topic_filter) == replacement

    assert repository.delete_subscription(replacement.topic_filter) == replacement
    assert repository.get_all_subscriptions() == []
    assert repository.is_updated
    database.dispose()


def test_subscription_repository_rejects_duplicate_topic_filters() -> None:
    database = DatabaseContext("sqlite:///:memory:")
    repository = SubscriptionRepository(database)
    subscription = Subscription("SmartHome/door/#")
    repository.create_subscription(subscription)

    with pytest.raises(ValueError, match="already exists"):
        repository.create_subscription(subscription)

    database.dispose()
