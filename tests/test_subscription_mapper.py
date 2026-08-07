from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.infrastructure.database.mappers.subscription_mapper import (
    SubscriptionMapper,
)
from smart_home_observer.infrastructure.database.models.subscription_row import (
    SubscriptionRow,
)


def test_subscription_mapper_creates_a_row_from_a_subscription() -> None:
    subscription = Subscription(
        "SmartHome/door/#",
        qos=2,
        retain_as_published=True,
        retain_handling=1,
    )

    row = SubscriptionMapper.to_subscription_row(subscription)

    assert row.topic_filter == subscription.topic_filter
    assert row.qos == subscription.qos
    assert row.retain_as_published == subscription.retain_as_published
    assert row.retain_handling == subscription.retain_handling


def test_subscription_mapper_creates_a_subscription_from_a_row() -> None:
    row = SubscriptionRow(
        topic_filter="SmartHome/door/#",
        qos=2,
        retain_as_published=True,
        retain_handling=1,
    )

    subscription = SubscriptionMapper.to_subscription(row)

    assert subscription == Subscription(
        "SmartHome/door/#",
        qos=2,
        retain_as_published=True,
        retain_handling=1,
    )
