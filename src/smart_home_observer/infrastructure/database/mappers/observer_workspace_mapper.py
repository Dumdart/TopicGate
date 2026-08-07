from smart_home_observer.core.models.observer_workspace import ObserverWorkspace
from smart_home_observer.core.models.observer_model import ObserverModel
from smart_home_observer.infrastructure.database.mappers.subscription_mapper import (
    SubscriptionMapper,
)
from smart_home_observer.infrastructure.database.models.observer_workspace_row import (
    ObserverWorkspaceRow,
)
from smart_home_observer.services.observer_model_service import ObserverModelService


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
        model = ObserverModel(root_stats=[])
        for subscription in subscriptions:
            ObserverModelService.find_or_create_node(model, subscription.topic_filter)
        return ObserverWorkspace(
            id=row.id,
            profile_id=row.profile_id,
            model=model,
            subscriptions=subscriptions,
        )
