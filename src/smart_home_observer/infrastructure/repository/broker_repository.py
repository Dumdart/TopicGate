from uuid import uuid4

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

        self._observer_workspace = ObserverWorkspace(
            id=uuid4(),
            profile_id=uuid4(),
            model=TopicService.get_topics(),
        )

        self._broker_profile = BrokerProfile(
            id=self._observer_workspace.profile_id,
            name="Default",
            config=self._settings.mqtt,
            workspace_id=self._observer_workspace.id,
            workspace=self._observer_workspace,
        )

    def get(self) -> AppConfig:
        """Return the temporary application configuration for the active profile."""
        return self._settings

    def update(self, settings: AppConfig) -> None:
        """Update the active profile's MQTT configuration."""
        self._settings = settings
        self._broker_profile.config = settings.mqtt
        self.save()

    def get_mqtt(self) -> MqttConfig:
        """Return the MQTT configuration required by the existing GUI contract."""
        return self._broker_profile.config

    def update_mqtt(self, mqtt: MqttConfig) -> None:
        """Update only the active profile's MQTT configuration."""
        self._settings.mqtt = mqtt
        self._broker_profile.config = mqtt
        self.save()

    def get_profile(self) -> BrokerProfile:
        return self._broker_profile

    def update_profile(self, profile: BrokerProfile) -> None:
        """Replace the active profile and retain its linked workspace."""
        self._broker_profile = profile
        self._observer_workspace = profile.workspace
        self._settings.mqtt = profile.config
        self.save()

    def get_observer_workspace(self) -> ObserverWorkspace:
        """Return the workspace associated with the active broker profile."""
        return self._observer_workspace

    def update_observer_workspace(self, workspace: ObserverWorkspace) -> None:
        """Replace the active profile's workspace."""
        if workspace.profile_id != self._broker_profile.id:
            raise ValueError("The workspace must belong to the active broker profile.")
        self._observer_workspace = workspace
        self._broker_profile.workspace_id = workspace.id
        self._broker_profile.workspace = workspace
        self.save()

    def get_observer_model(self) -> ObserverModel:
        """Return the observer model associated with the active broker profile."""
        return self._observer_workspace.model

    def update_observer_model(self, model: ObserverModel) -> None:
        """Replace the active profile's observer model."""
        self._observer_workspace.model = model
        self.save()

    def save(self) -> None:
        """Persist profiles and workspaces when durable storage is introduced."""
