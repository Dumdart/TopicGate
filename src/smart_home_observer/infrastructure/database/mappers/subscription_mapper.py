from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.infrastructure.database.mappers.mapper_helper import (
    MapperHelper,
)
from smart_home_observer.infrastructure.database.models.subscription_row import (
    SubscriptionRow,
)


class SubscriptionMapper:
    """Converts between MQTT subscriptions and database rows."""

    @staticmethod
    def to_subscription_row(subscription: Subscription) -> SubscriptionRow:
        return SubscriptionRow(
            topic_filter=subscription.topic_filter,
            qos=subscription.qos,
            retain_as_published=subscription.retain_as_published,
            retain_handling=subscription.retain_handling,
        )

    @staticmethod
    def to_subscription(subscription_row: SubscriptionRow) -> Subscription:
        return Subscription(
            topic_filter=MapperHelper.required_str(
                subscription_row.topic_filter,
                "topic_filter",
            ),
            qos=MapperHelper.required_int(subscription_row.qos, "qos"),
            retain_as_published=MapperHelper.required_bool(
                subscription_row.retain_as_published,
                "retain_as_published",
            ),
            retain_handling=MapperHelper.required_int(
                subscription_row.retain_handling,
                "retain_handling",
            ),
        )
