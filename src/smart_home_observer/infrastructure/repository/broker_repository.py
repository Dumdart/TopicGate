from uuid import UUID, uuid4

from smart_home_observer.core.config.app_config import AppConfig
from smart_home_observer.core.config.config_loader import ConfigLoader
from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.broker_profile import BrokerProfile
from smart_home_observer.core.models.observer_model import ObserverModel
from smart_home_observer.core.models.observer_workspace import ObserverWorkspace
from smart_home_observer.services.topic_service import TopicService


class BrokerRepository:
    """Temporary in-memory store for broker profiles and their workspaces."""

    def __init__(self, settings: AppConfig | None = None) -> None:
        self._settings = settings or ConfigLoader().load_config()
        default_profile = self._create_profile("Default", self._settings.mqtt)
        local_profile = self._create_profile(
            "Local MQTT",
            MqttConfig("localhost", 1883, "", ""),
        )
        self._profiles = {
            default_profile.id: default_profile,
            local_profile.id: local_profile,
        }
        self._active_profile_id = default_profile.id

    def get(self) -> AppConfig:
        """Return the temporary application configuration for the active profile."""
        return self._settings

    def update(self, settings: AppConfig) -> None:
        """Update the active profile's MQTT configuration."""
        self._settings = settings
        self._active_profile.config = settings.mqtt
        self.save()

    def get_mqtt(self) -> MqttConfig:
        """Return the MQTT configuration required by the existing GUI contract."""
        return self._active_profile.config

    def update_mqtt(self, mqtt: MqttConfig) -> None:
        """Update only the active profile's MQTT configuration."""
        self.activate_profile(self._active_profile_id, mqtt)

    def get_profile(self, profile_id: UUID | None = None) -> BrokerProfile:
        """Return the active profile, or the profile identified by ``profile_id``."""
        return self._profiles[profile_id or self._active_profile_id]

    def get_all_profiles(self) -> tuple[BrokerProfile, ...]:
        """Return every available broker profile in display order."""
        return tuple(self._profiles.values())

    def update_profile(self, profile: BrokerProfile) -> None:
        """Replace a broker profile while retaining its linked workspace."""
        self._profiles[profile.id] = profile
        if profile.id == self._active_profile_id:
            self._settings.mqtt = profile.config
        self.save()

    def activate_profile(self, profile_id: UUID, mqtt: MqttConfig | None = None) -> None:
        """Make a profile active after its MQTT connection has been updated."""
        profile = self.get_profile(profile_id)
        if mqtt is not None:
            profile.config = mqtt
        self._active_profile_id = profile.id
        self._settings.mqtt = profile.config
        self.save()

    def get_observer_workspace(self) -> ObserverWorkspace:
        """Return the workspace associated with the active broker profile."""
        return self._active_profile.workspace

    def update_observer_workspace(self, workspace: ObserverWorkspace) -> None:
        """Replace the active profile's workspace."""
        if workspace.profile_id != self._active_profile.id:
            raise ValueError("The workspace must belong to the active broker profile.")
        self._active_profile.workspace_id = workspace.id
        self._active_profile.workspace = workspace
        self.save()

    def get_observer_model(self) -> ObserverModel:
        """Return the observer model associated with the active broker profile."""
        return self._active_profile.workspace.model

    def update_observer_model(self, model: ObserverModel) -> None:
        """Replace the active profile's observer model."""
        self._active_profile.workspace.model = model
        self.save()

    def save(self) -> None:
        """Persist profiles and workspaces when durable storage is introduced."""

    @property
    def _active_profile(self) -> BrokerProfile:
        return self._profiles[self._active_profile_id]

    @staticmethod
    def _create_profile(name: str, config: MqttConfig) -> BrokerProfile:
        profile_id = uuid4()
        workspace = ObserverWorkspace(
            id=uuid4(),
            profile_id=profile_id,
            model=TopicService.get_topics(),
        )
        return BrokerProfile(
            id=profile_id,
            name=name,
            config=config,
            workspace_id=workspace.id,
            workspace=workspace,
        )
