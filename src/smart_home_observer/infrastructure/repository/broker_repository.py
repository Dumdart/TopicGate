from uuid import UUID, uuid4

from sqlalchemy import select

from smart_home_observer.core.config.app_config import AppConfig
from smart_home_observer.core.config.config_loader import ConfigLoader
from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.broker_profile import BrokerProfile
from smart_home_observer.core.models.observer_model import ObserverModel
from smart_home_observer.core.models.observer_workspace import ObserverWorkspace
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.infrastructure.database.database_context import DatabaseContext
from smart_home_observer.infrastructure.database.mappers.broker_profile_mapper import (
    BrokerProfileMapper,
)
from smart_home_observer.infrastructure.database.models.broker_profile_row import (
    BrokerProfileRow,
)
from smart_home_observer.services.observer_model_service import ObserverModelService
from smart_home_observer.services.topic_service import TopicService


class BrokerRepository:
    """Persists broker profiles, workspaces, and workspace subscriptions."""

    def __init__(
        self,
        settings: AppConfig | DatabaseContext | None = None,
        db: DatabaseContext | AppConfig | None = None,
    ) -> None:
        # Check both argument orders while retaining the original settings-only API.
        if isinstance(settings, DatabaseContext):
            self._db = settings
            supplied_settings = db if isinstance(db, AppConfig) else None
        else:
            self._db = db if isinstance(db, DatabaseContext) else DatabaseContext(
                "sqlite:///:memory:"
            )
            supplied_settings = settings

        profiles, active_profile_id = self._load_profiles()
        if profiles:
            self._profiles = {profile.id: profile for profile in profiles}
            self._active_profile_id = active_profile_id or profiles[0].id
            self._settings = supplied_settings or AppConfig(self._active_profile.config)
            self._settings.mqtt = self._active_profile.config
            return

        self._settings = supplied_settings or ConfigLoader().load_config()
        default_profile = self._create_profile(
            "Default",
            self._settings.mqtt,
            TopicService.get_topics(),
        )
        local_profile = self._create_profile(
            "Local MQTT",
            MqttConfig("localhost", 1883, "", ""),
            TopicService.get_topics2(),
        )
        self._profiles = {
            default_profile.id: default_profile,
            local_profile.id: local_profile,
        }
        self._active_profile_id = default_profile.id
        self.save()

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

    def create_profile(self, name: str, config: MqttConfig) -> BrokerProfile:
        """Create a broker profile with an independent, empty workspace."""
        normalized_name = self._validate_profile_name(name)
        profile = self._create_profile(
            normalized_name,
            config,
            ObserverModel(root_stats=[]),
        )
        self._profiles[profile.id] = profile
        self.save()
        return profile

    def update_profile(self, profile: BrokerProfile) -> None:
        """Replace a broker profile while retaining its linked workspace."""
        if profile.id not in self._profiles:
            raise KeyError(f"Unknown broker profile: {profile.id}")
        profile.name = self._validate_profile_name(profile.name, profile.id)
        if (
            profile.workspace.profile_id != profile.id
            or profile.workspace_id != profile.workspace.id
        ):
            raise ValueError("The workspace must belong to the broker profile.")
        self._profiles[profile.id] = profile
        if profile.id == self._active_profile_id:
            self._settings.mqtt = profile.config
        self.save()

    def delete_profile(self, profile_id: UUID) -> BrokerProfile:
        """Delete an inactive profile while retaining at least one profile."""
        if profile_id == self._active_profile_id:
            raise ValueError("The active broker profile cannot be deleted.")
        if len(self._profiles) == 1:
            raise ValueError("At least one broker profile is required.")
        profile = self._profiles.pop(profile_id)
        self.save()
        return profile

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
        """Replace runtime state; only its derived subscriptions are persisted."""
        self._active_profile.workspace.model = model
        self.save()

    def save(self) -> None:
        """Persist profiles and subscription lists, excluding runtime topic state."""
        with self._db.session() as session:
            existing_rows = session.scalars(select(BrokerProfileRow)).all()
            for row in existing_rows:
                session.delete(row)
            session.flush()
            session.add_all(
                BrokerProfileMapper.to_broker_profile_row(
                    profile,
                    position=position,
                    is_active=profile.id == self._active_profile_id,
                )
                for position, profile in enumerate(self._profiles.values())
            )
            session.commit()

    def _load_profiles(self) -> tuple[list[BrokerProfile], UUID | None]:
        with self._db.session() as session:
            rows = session.scalars(
                select(BrokerProfileRow).order_by(BrokerProfileRow.position)
            ).all()
            profiles = [BrokerProfileMapper.to_broker_profile(row) for row in rows]
            active_profile_id = next(
                (row.id for row in rows if row.is_active),
                None,
            )
            return profiles, active_profile_id

    @property
    def _active_profile(self) -> BrokerProfile:
        return self._profiles[self._active_profile_id]

    @staticmethod
    def _create_profile(
        name: str,
        config: MqttConfig,
        observer_model: ObserverModel,
    ) -> BrokerProfile:
        profile_id = uuid4()
        workspace = ObserverWorkspace(
            id=uuid4(),
            profile_id=profile_id,
            model=observer_model,
            subscriptions=tuple(
                Subscription(topic_filter)
                for topic_filter in ObserverModelService.get_all_topics(
                    observer_model
                )
            ),
        )
        return BrokerProfile(
            id=profile_id,
            name=name,
            config=config,
            workspace_id=workspace.id,
            workspace=workspace,
        )

    def _validate_profile_name(
        self,
        name: str,
        profile_id: UUID | None = None,
    ) -> str:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("A broker profile name is required.")
        if any(
            profile.id != profile_id
            and profile.name.casefold() == normalized_name.casefold()
            for profile in self._profiles.values()
        ):
            raise ValueError("A broker profile with that name already exists.")
        return normalized_name
