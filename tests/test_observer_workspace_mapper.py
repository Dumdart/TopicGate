from uuid import uuid4

from smart_home_observer.core.models.observer_model import ObserverModel
from smart_home_observer.core.models.observer_workspace import ObserverWorkspace
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.infrastructure.database.mappers.observer_workspace_mapper import (
    ObserverWorkspaceMapper,
)
from smart_home_observer.services.observer_model_service import ObserverModelService


def test_workspace_mapper_reconstructs_the_tree_from_subscriptions() -> None:
    profile_id = uuid4()
    workspace = ObserverWorkspace(
        id=uuid4(),
        profile_id=profile_id,
        model=ObserverModel(root_stats=[]),
        subscriptions=(
            Subscription("SmartHome/+/status", qos=2),
            Subscription("bridge/#"),
        ),
    )

    row = ObserverWorkspaceMapper.to_observer_workspace_row(workspace)
    mapped = ObserverWorkspaceMapper.to_observer_workspace(row)

    assert mapped.id == workspace.id
    assert mapped.profile_id == profile_id
    assert mapped.subscriptions == workspace.subscriptions
    assert ObserverModelService.get_all_topics(mapped.model) == [
        "SmartHome/+/status",
        "bridge/#",
    ]
    assert mapped.model.topic_states == {}

