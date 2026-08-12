from typing import Protocol
from uuid import UUID

from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.broker_profile import BrokerProfile
from topicgate.core.models.observer_model import ObserverModel
from topicgate.core.models.observer_workspace import ObserverWorkspace


class BrokerProfileStore(Protocol):
    """Store broker profiles and their observer workspaces."""

    def get_profile(self, profile_id: UUID | None = None, /) -> BrokerProfile: ...

    def get_all_profiles(self) -> tuple[BrokerProfile, ...]: ...

    def create_profile(self, name: str, mqtt: MqttConfig, /) -> BrokerProfile: ...

    def update_profile(self, profile: BrokerProfile, /) -> None: ...

    def delete_profile(self, profile_id: UUID, /) -> BrokerProfile: ...

    def activate_profile(
        self,
        profile_id: UUID,
        mqtt: MqttConfig | None = None,
        /,
    ) -> None: ...

    def update_observer_workspace(
        self,
        workspace: ObserverWorkspace,
        /,
    ) -> None: ...

    def update_observer_model(self, model: ObserverModel, /) -> None: ...
