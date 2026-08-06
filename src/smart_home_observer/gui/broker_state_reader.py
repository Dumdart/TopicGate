from typing import Protocol
from uuid import UUID

from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.broker_profile import BrokerProfile


class BrokerStateReader(Protocol):
    """Provides settings for the active broker profile to the UI."""

    def get_mqtt(self) -> MqttConfig: ...

    def update_mqtt(self, mqtt: MqttConfig) -> None: ...

    def get_profile(self, profile_id: UUID | None = None) -> BrokerProfile: ...

    def get_all_profiles(self) -> tuple[BrokerProfile, ...]: ...

    def create_profile(self, name: str, config: MqttConfig) -> BrokerProfile: ...

    def update_profile(self, profile: BrokerProfile) -> None: ...

    def delete_profile(self, profile_id: UUID) -> BrokerProfile: ...

    def activate_profile(
        self,
        profile_id: UUID,
        mqtt: MqttConfig | None = None,
    ) -> None: ...
