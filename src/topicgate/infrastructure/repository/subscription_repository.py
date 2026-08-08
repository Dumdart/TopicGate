
from topicgate.core.models.subscription import Subscription
from topicgate.infrastructure.database.database_context import DatabaseContext
from sqlalchemy import select

from topicgate.infrastructure.database.mappers.subscription_mapper import (
    SubscriptionMapper,
)
from topicgate.infrastructure.database.models.subscription_row import (
    SubscriptionRow,
)


class SubscriptionRepository:
    """Persists MQTT subscriptions using their topic filter as the unique key."""

    def __init__(
        self,
        db: DatabaseContext,
        subscriptions: list[Subscription] | None = None,
    ) -> None:
        self._db = db
        self.is_updated = False
        for subscription in subscriptions or []:
            if self.get_subscription_by_topic(subscription.topic_filter) is None:
                self.create_subscription(subscription)

    def get_subscription_by_topic(self, topic_filter: str) -> Subscription | None:
        with self._db.session() as session:
            row = session.scalar(
                select(SubscriptionRow).where(
                    SubscriptionRow.topic_filter == topic_filter
                )
            )
            return SubscriptionMapper.to_subscription(row) if row else None

    def get_subscription_by_id(self, subscription_id: int) -> Subscription | None:
        with self._db.session() as session:
            row = session.scalar(
                select(SubscriptionRow).where(SubscriptionRow.id == subscription_id)
            )
            return SubscriptionMapper.to_subscription(row) if row else None

    def get_all_subscriptions(self) -> list[Subscription]:
        with self._db.session() as session:
            rows = session.scalars(
                select(SubscriptionRow).order_by(SubscriptionRow.id)
            ).all()
            return [SubscriptionMapper.to_subscription(row) for row in rows]

    def create_subscription(self, subscription: Subscription) -> Subscription:
        if self.get_subscription_by_topic(subscription.topic_filter) is not None:
            raise ValueError(
                f"A subscription for {subscription.topic_filter!r} already exists."
            )

        with self._db.session() as session:
            session.add(SubscriptionMapper.to_subscription_row(subscription))
            session.commit()
            self.is_updated = True
        return subscription

    def update_subscription(
        self,
        topic_filter: str,
        subscription: Subscription,
    ) -> Subscription:
        with self._db.session() as session:
            row = session.scalar(
                select(SubscriptionRow).where(
                    SubscriptionRow.topic_filter == topic_filter
                )
            )
            if row is None:
                raise KeyError(f"Unknown subscription {topic_filter!r}.")

            if subscription.topic_filter != topic_filter:
                existing = session.scalar(
                    select(SubscriptionRow).where(
                        SubscriptionRow.topic_filter == subscription.topic_filter
                    )
                )
                if existing is not None:
                    raise ValueError(
                        f"A subscription for {subscription.topic_filter!r} already exists."
                    )

            row.topic_filter = subscription.topic_filter
            row.qos = subscription.qos
            row.retain_as_published = subscription.retain_as_published
            row.retain_handling = subscription.retain_handling
            session.commit()
            self.is_updated = True
        return subscription

    def delete_subscription(self, topic_filter: str) -> Subscription:
        with self._db.session() as session:
            row = session.scalar(
                select(SubscriptionRow).where(
                    SubscriptionRow.topic_filter == topic_filter
                )
            )
            if row is None:
                raise KeyError(f"Unknown subscription {topic_filter!r}.")

            subscription = SubscriptionMapper.to_subscription(row)
            session.delete(row)
            session.commit()
            self.is_updated = True
        return subscription
