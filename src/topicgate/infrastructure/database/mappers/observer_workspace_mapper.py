from topicgate.core.models.observer_workspace import ObserverWorkspace
from topicgate.infrastructure.database.mappers.subscription_mapper import (
    SubscriptionMapper,
)
from topicgate.infrastructure.database.models.observer_workspace_row import (
    ObserverWorkspaceRow,
)


class ObserverWorkspaceMapper:
    """Maps persisted observer workspace identity and subscriptions."""

    @staticmethod
    def to_observer_workspace_row(workspace: ObserverWorkspace) -> ObserverWorkspaceRow:
        row = ObserverWorkspaceRow(
            id=workspace.id,
            profile_id=workspace.profile_id,
        )
        row.subscriptions = [
            SubscriptionMapper.to_subscription_row(subscription)
            for subscription in workspace.subscriptions
        ]
        return row

    @staticmethod
    def to_observer_workspace(row: ObserverWorkspaceRow) -> ObserverWorkspace:
        subscriptions = tuple(
            SubscriptionMapper.to_subscription(subscription)
            for subscription in row.subscriptions
        )
        return ObserverWorkspace(
            id=row.id,
            profile_id=row.profile_id,
            subscriptions=subscriptions,
        )
