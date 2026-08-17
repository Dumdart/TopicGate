from topicgate.core.models.observer_workspace import ObserverWorkspace
from topicgate.core.models.observer_model import ObserverModel
from topicgate.infrastructure.database.mappers.subscription_mapper import (
    SubscriptionMapper,
)
from topicgate.infrastructure.database.models.observer_workspace_row import (
    ObserverWorkspaceRow,
)
from topicgate.processors.observer_model_processor import ObserverModelProcessor


class ObserverWorkspaceMapper:
    """Persists subscriptions and reconstructs the runtime observer tree."""

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
        model = ObserverModelProcessor.add_topics(
            ObserverModel(root_stats=[]),
            (subscription.topic_filter for subscription in subscriptions),
        )
        return ObserverWorkspace(
            id=row.id,
            profile_id=row.profile_id,
            model=model,
            subscriptions=subscriptions,
        )
