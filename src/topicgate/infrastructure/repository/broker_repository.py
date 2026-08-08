from dataclasses import replace
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from topicgate.core.config.app_config import AppConfig
from topicgate.core.config.config_loader import ConfigLoader
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.broker_profile import BrokerProfile
from topicgate.core.models.observer_model import ObserverModel
from topicgate.core.models.observer_workspace import ObserverWorkspace
from topicgate.core.models.subscription import Subscription
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.database.mappers.broker_profile_mapper import (
    BrokerProfileMapper,
)
from topicgate.infrastructure.database.mappers.subscription_mapper import (
    SubscriptionMapper,
)
from topicgate.infrastructure.database.models.broker_profile_row import (
    BrokerProfileRow,
)
from topicgate.infrastructure.database.models.observer_workspace_row import (
    ObserverWorkspaceRow,
)
class BrokerRepository:
    """Persist broker profiles and use the database as their source of truth."""

    def __init__(
        self,
        settings: AppConfig | DatabaseContext | None = None,
        db: DatabaseContext | AppConfig | None = None,
    ) -> None:
        if isinstance(settings, DatabaseContext):
            self._db = settings
            supplied_settings = db if isinstance(db, AppConfig) else None
        else:
            self._db = db if isinstance(db, DatabaseContext) else DatabaseContext(
                "sqlite:///:memory:"
            )
            supplied_settings = settings

        self._runtime_configs: dict[UUID, MqttConfig] = {}
        self._runtime_models: dict[UUID, ObserverModel] = {}
        self._profile_handles: dict[UUID, BrokerProfile] = {}

        profiles = self.get_all_profiles()
        if profiles:
            active_profile = self.get_profile()
            if supplied_settings is not None:
                self._runtime_configs[active_profile.id] = supplied_settings.mqtt
                self._settings = supplied_settings
            else:
                self._settings = AppConfig(active_profile.config)
            return

        self._settings = supplied_settings or ConfigLoader().load_config()
        default_profile = self._create_profile(
            "Default",
            self._settings.mqtt,
        )
        local_profile = self._create_profile(
            "Local MQTT",
            MqttConfig("localhost", 1883, "", ""),
        )
        self._runtime_configs[default_profile.id] = default_profile.config
        self._runtime_configs[local_profile.id] = local_profile.config
        with self._db.session() as session:
            session.add(
                BrokerProfileMapper.to_broker_profile_row(
                    default_profile,
                    position=0,
                    is_active=True,
                )
            )
            session.add(
                BrokerProfileMapper.to_broker_profile_row(
                    local_profile,
                    position=1,
                    is_active=False,
                )
            )
            session.commit()
        self.save()

    def get(self) -> AppConfig:
        """Return application settings backed by the active database profile."""
        mqtt = self.get_mqtt()
        if self._settings.mqtt != mqtt:
            self._settings = AppConfig(mqtt=mqtt, id=self._settings.id)
        return self._settings

    def update(self, settings: AppConfig) -> None:
        """Update the active profile's MQTT configuration."""
        self.update_mqtt(settings.mqtt)
        self._settings = settings

    def get_mqtt(self) -> MqttConfig:
        """Return the active profile's current MQTT configuration."""
        return self.get_profile().config

    def update_mqtt(self, mqtt: MqttConfig) -> None:
        """Update only the active profile's MQTT configuration."""
        self.activate_profile(self.get_profile().id, mqtt)

    def get_profile(self, profile_id: UUID | None = None) -> BrokerProfile:
        """Read the active profile, or a selected profile, from the database."""
        with self._db.session() as session:
            statement = self._profile_statement()
            if profile_id is None:
                statement = statement.where(BrokerProfileRow.is_active.is_(True))
            else:
                statement = statement.where(BrokerProfileRow.id == profile_id)
            row = session.scalar(statement)
            if row is None:
                identifier = "active profile" if profile_id is None else profile_id
                raise KeyError(f"Unknown broker profile: {identifier}")
            return self._to_profile(row)

    def get_all_profiles(self) -> tuple[BrokerProfile, ...]:
        """Read every broker profile from the database in display order."""
        with self._db.session() as session:
            rows = session.scalars(
                self._profile_statement().order_by(BrokerProfileRow.position)
            ).all()
            return tuple(self._to_profile(row) for row in rows)

    def create_profile(self, name: str, config: MqttConfig) -> BrokerProfile:
        """Create a broker profile with an independent, empty workspace."""
        normalized_name = self._validate_profile_name(name)
        profile = self._create_profile(
            normalized_name,
            config,
        )
        with self._db.session() as session:
            positions = session.scalars(select(BrokerProfileRow.position)).all()
            session.add(
                BrokerProfileMapper.to_broker_profile_row(
                    profile,
                    position=max(positions, default=-1) + 1,
                )
            )
            session.commit()
        self._runtime_configs[profile.id] = config
        self._profile_handles[profile.id] = profile
        self.save()
        return profile

    def update_profile(self, profile: BrokerProfile) -> None:
        """Persist changes to a broker profile and its workspace."""
        normalized_name = self._validate_profile_name(profile.name, profile.id)
        if (
            profile.workspace.profile_id != profile.id
            or profile.workspace_id != profile.workspace.id
        ):
            raise ValueError("The workspace must belong to the broker profile.")

        with self._db.session() as session:
            row = session.scalar(
                self._profile_statement().where(BrokerProfileRow.id == profile.id)
            )
            if row is None:
                raise KeyError(f"Unknown broker profile: {profile.id}")
            if row.workspace.id != profile.workspace.id:
                raise ValueError("A broker profile's workspace cannot be replaced.")
            row.name = normalized_name
            self._update_mqtt_row(row, profile.config)
            self._replace_subscriptions(
                session,
                row.workspace,
                profile.workspace.subscriptions,
            )
            session.commit()

        profile.name = normalized_name
        self._runtime_configs[profile.id] = profile.config
        self._profile_handles[profile.id] = profile
        if self.get_profile().id == profile.id:
            self._settings = AppConfig(profile.config, id=self._settings.id)
        self.save()

    def delete_profile(self, profile_id: UUID) -> BrokerProfile:
        """Delete an inactive profile while retaining at least one profile."""
        with self._db.session() as session:
            rows = session.scalars(self._profile_statement()).all()
            row = next((item for item in rows if item.id == profile_id), None)
            if row is None:
                raise KeyError(f"Unknown broker profile: {profile_id}")
            if row.is_active:
                raise ValueError("The active broker profile cannot be deleted.")
            if len(rows) == 1:
                raise ValueError("At least one broker profile is required.")
            profile = self._profile_handles.get(profile_id) or self._to_profile(row)
            session.delete(row)
            session.commit()

        self._runtime_configs.pop(profile_id, None)
        self._runtime_models.pop(profile_id, None)
        self._profile_handles.pop(profile_id, None)
        self.save()
        return profile

    def activate_profile(self, profile_id: UUID, mqtt: MqttConfig | None = None) -> None:
        """Persist the active profile after its MQTT connection was updated."""
        with self._db.session() as session:
            rows = session.scalars(self._profile_statement()).all()
            selected = next((row for row in rows if row.id == profile_id), None)
            if selected is None:
                raise KeyError(f"Unknown broker profile: {profile_id}")
            for row in rows:
                row.is_active = row.id == profile_id
            if mqtt is not None:
                self._update_mqtt_row(selected, mqtt)
            session.commit()

        if mqtt is not None:
            self._runtime_configs[profile_id] = mqtt
        active_config = self.get_mqtt()
        self._settings = AppConfig(active_config, id=self._settings.id)
        self.save()

    def get_observer_workspace(self) -> ObserverWorkspace:
        """Read the active profile's workspace from the database."""
        return self.get_profile().workspace

    def update_observer_workspace(self, workspace: ObserverWorkspace) -> None:
        """Persist the active workspace's subscription list."""
        active_profile = self.get_profile()
        if workspace.profile_id != active_profile.id:
            raise ValueError("The workspace must belong to the active broker profile.")
        if workspace.id != active_profile.workspace.id:
            raise ValueError("The active broker profile's workspace cannot be replaced.")

        with self._db.session() as session:
            row = session.scalar(
                select(ObserverWorkspaceRow)
                .options(selectinload(ObserverWorkspaceRow.subscriptions))
                .where(ObserverWorkspaceRow.id == workspace.id)
            )
            if row is None:
                raise KeyError(f"Unknown observer workspace: {workspace.id}")
            self._replace_subscriptions(session, row, workspace.subscriptions)
            session.commit()

        self.save()

    def get_observer_model(self) -> ObserverModel:
        """Return the active profile's runtime observer model."""
        return self.get_profile().workspace.model

    def update_observer_model(self, model: ObserverModel) -> None:
        """Retain runtime topic state without writing transient messages to SQLite."""
        active_profile = self.get_profile()
        self._runtime_models[active_profile.id] = model
        self.save()

    def save(self) -> None:
        """Compatibility hook; mutating operations commit their own transaction."""

    @staticmethod
    def _profile_statement():
        return select(BrokerProfileRow).options(
            selectinload(BrokerProfileRow.config),
            selectinload(BrokerProfileRow.workspace).selectinload(
                ObserverWorkspaceRow.subscriptions
            ),
        )

    def _to_profile(self, row: BrokerProfileRow) -> BrokerProfile:
        profile = BrokerProfileMapper.to_broker_profile(row)
        runtime_config = self._runtime_configs.get(profile.id)
        if runtime_config is not None:
            profile.config = replace(
                profile.config,
                password=runtime_config.password,
                id=runtime_config.id,
            )
        runtime_model = self._runtime_models.get(profile.id)
        if runtime_model is not None:
            profile.workspace.model = runtime_model
        return profile

    @staticmethod
    def _update_mqtt_row(row: BrokerProfileRow, config: MqttConfig) -> None:
        row.config.host = config.host
        row.config.port = config.port
        row.config.username = config.username
        row.config.use_tls = config.use_tls

    @staticmethod
    def _replace_subscriptions(
        session,
        workspace: ObserverWorkspaceRow,
        subscriptions: tuple[Subscription, ...],
    ) -> None:
        previous_rows = list(workspace.subscriptions)
        workspace.subscriptions = []
        session.flush()
        for row in previous_rows:
            session.delete(row)
        workspace.subscriptions = [
            SubscriptionMapper.to_subscription_row(subscription)
            for subscription in subscriptions
        ]

    @staticmethod
    def _create_profile(
        name: str,
        config: MqttConfig,
    ) -> BrokerProfile:
        profile_id = uuid4()
        workspace = ObserverWorkspace(
            id=uuid4(),
            profile_id=profile_id,
            model=ObserverModel(root_stats=[]),
            subscriptions=(),
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
        with self._db.session() as session:
            rows = session.execute(
                select(BrokerProfileRow.id, BrokerProfileRow.name)
            ).all()
        if any(
            row.id != profile_id
            and row.name.casefold() == normalized_name.casefold()
            for row in rows
        ):
            raise ValueError("A broker profile with that name already exists.")
        return normalized_name
