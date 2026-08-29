from uuid import uuid4

from topicgate.core.models.observer_workspace import ObserverWorkspace
from topicgate.core.models.subscription import Subscription
from topicgate.infrastructure.database.mappers.observer_workspace_mapper import (
    ObserverWorkspaceMapper,
)


def test_workspace_mapper_round_trips_subscriptions() -> None:
    profile_id = uuid4()
    workspace = ObserverWorkspace(
        id=uuid4(),
        profile_id=profile_id,
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

