from topicgate.core.models.broker_profile import BrokerProfile
from topicgate.infrastructure.database.mappers.config_mapper import ConfigMapper
from topicgate.infrastructure.database.mappers.observer_workspace_mapper import (
    ObserverWorkspaceMapper,
)
from topicgate.infrastructure.database.models.broker_profile_row import (
    BrokerProfileRow,
)


class BrokerProfileMapper:
    """Converts complete broker profile aggregates to database rows."""

    @staticmethod
    def to_broker_profile_row(
        profile: BrokerProfile,
        *,
        position: int = 0,
        is_active: bool = False,
    ) -> BrokerProfileRow:
        row = BrokerProfileRow(
            id=profile.id,
            name=profile.name,
            position=position,
            is_active=is_active,
        )
        row.config = ConfigMapper.to_mqtt_config_row(profile.config)
        row.workspace = ObserverWorkspaceMapper.to_observer_workspace_row(
            profile.workspace
        )
        return row

    @staticmethod
    def to_broker_profile(row: BrokerProfileRow) -> BrokerProfile:
        workspace = ObserverWorkspaceMapper.to_observer_workspace(row.workspace)
        return BrokerProfile(
            id=row.id,
            name=row.name,
            config=ConfigMapper.to_mqtt_config(row.config),
            workspace_id=workspace.id,
            workspace=workspace,
        )
