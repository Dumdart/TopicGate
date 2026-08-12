from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from topicgate.core.models.subscription import Subscription
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.database.mappers.subscription_mapper import SubscriptionMapper
from topicgate.infrastructure.database.models.observer_workspace_row import (
    ObserverWorkspaceRow,
)


class SubscriptionRepository:
    """Persist subscriptions within an observer workspace boundary."""

    def __init__(self, db: DatabaseContext) -> None:
        self._db = db

    def list_for_workspace(self, workspace_id: UUID) -> tuple[Subscription, ...]:
        with self._db.session() as session:
            workspace = self._workspace(session, workspace_id)
            return tuple(
                SubscriptionMapper.to_subscription(row)
                for row in workspace.subscriptions
            )

    def add(self, workspace_id: UUID, subscription: Subscription) -> Subscription:
        with self._db.session() as session:
            workspace = self._workspace(session, workspace_id)
            if self._find(workspace, subscription.topic_filter) is not None:
                raise ValueError(
                    f"A subscription for {subscription.topic_filter!r} already exists."
                )
            workspace.subscriptions.append(
                SubscriptionMapper.to_subscription_row(subscription)
            )
            session.commit()
            return subscription

    def update(
        self,
        workspace_id: UUID,
        original_filter: str,
        subscription: Subscription,
    ) -> Subscription:
        with self._db.session() as session:
            workspace = self._workspace(session, workspace_id)
            row = self._find(workspace, original_filter)
            if row is None:
                raise KeyError(f"Unknown subscription {original_filter!r}.")
            duplicate = self._find(workspace, subscription.topic_filter)
            if duplicate is not None and duplicate is not row:
                raise ValueError(
                    f"A subscription for {subscription.topic_filter!r} already exists."
                )
            row.topic_filter = subscription.topic_filter
            row.qos = subscription.qos
            row.retain_as_published = subscription.retain_as_published
            row.retain_handling = subscription.retain_handling
            session.commit()
            return subscription

    def remove(self, workspace_id: UUID, topic_filter: str) -> Subscription:
        with self._db.session() as session:
            workspace = self._workspace(session, workspace_id)
            row = self._find(workspace, topic_filter)
            if row is None:
                raise KeyError(f"Unknown subscription {topic_filter!r}.")
            subscription = SubscriptionMapper.to_subscription(row)
            workspace.subscriptions.remove(row)
            session.delete(row)
            session.commit()
            return subscription

    def replace_all(
        self,
        workspace_id: UUID,
        subscriptions: tuple[Subscription, ...],
    ) -> None:
        filters = [item.topic_filter for item in subscriptions]
        if len(filters) != len(set(filters)):
            raise ValueError("Subscription topic filters must be unique per workspace.")
        with self._db.session() as session:
            workspace = self._workspace(session, workspace_id)
            previous_rows = list(workspace.subscriptions)
            workspace.subscriptions = []
            session.flush()
            for row in previous_rows:
                session.delete(row)
            workspace.subscriptions = [
                SubscriptionMapper.to_subscription_row(item)
                for item in subscriptions
            ]
            session.commit()

    @staticmethod
    def _workspace(session, workspace_id: UUID) -> ObserverWorkspaceRow:
        workspace = session.scalar(
            select(ObserverWorkspaceRow)
            .options(selectinload(ObserverWorkspaceRow.subscriptions))
            .where(ObserverWorkspaceRow.id == workspace_id)
        )
        if workspace is None:
            raise KeyError(f"Unknown observer workspace: {workspace_id}")
        return workspace

    @staticmethod
    def _find(workspace: ObserverWorkspaceRow, topic_filter: str):
        return next(
            (
                row
                for row in workspace.subscriptions
                if row.topic_filter == topic_filter
            ),
            None,
        )
