from dataclasses import replace
from uuid import UUID

from topicgate.app.broker_runtime_state import BrokerRuntimeState
from topicgate.core.config.app_config import AppConfig
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.broker_profile import BrokerProfile
from topicgate.core.models.observer_model import ObserverModel
from topicgate.core.models.observer_workspace import ObserverWorkspace
from topicgate.infrastructure.credentials.credential_store import CredentialStore
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.repository.broker_config_repository import (
    BrokerConfigRepository,
)
from topicgate.infrastructure.repository.broker_repository import BrokerRepository
from topicgate.infrastructure.repository.subscription_repository import (
    SubscriptionRepository,
)
from topicgate.infrastructure.repository.topic_message_repository import TopicMessageRepository
from topicgate.processors.observer_model_processor import ObserverModelProcessor


class BrokerProfileService:
    """Compose broker identity, persisted config, credentials, and runtime state."""

    def __init__(
        self,
        settings: AppConfig | DatabaseContext | None = None,
        db: DatabaseContext | AppConfig | None = None,
        *,
        credential_store: CredentialStore,
        runtime_state: BrokerRuntimeState | None = None,
    ) -> None:
        if isinstance(settings, DatabaseContext):
            self._db = settings
            supplied_settings = db if isinstance(db, AppConfig) else None
        else:
            self._db = db if isinstance(db, DatabaseContext) else DatabaseContext(
                "sqlite:///:memory:"
            )
            supplied_settings = settings
        self._credentials = credential_store
        self._runtime_state = runtime_state or BrokerRuntimeState()
        self.brokers = BrokerRepository(self._db)
        self.configs = BrokerConfigRepository(self._db)
        self.subscriptions = SubscriptionRepository(self._db)
        self._topic_messages = TopicMessageRepository(self._db)
        self._settings_id = supplied_settings.id if supplied_settings else None

        identities = self.brokers.list_profiles()
        if not identities:
            initial = supplied_settings.mqtt if supplied_settings else MqttConfig(
                "localhost", 1883, "", ""
            )
            self._create_seed_profile("Default", initial, is_active=True)
            self._create_seed_profile(
                "Local MQTT", MqttConfig("localhost", 1883, "", "")
            )
        elif supplied_settings is not None:
            active_id = self.brokers.get_profile().id
            if self._credentials.get_password(active_id) is None:
                self._store_password(active_id, supplied_settings.mqtt.password)

        self._settings = (
            supplied_settings
            if supplied_settings is not None and not identities
            else AppConfig(self.get_profile().config, id=self._settings_id)
        )

    def get_profile(self, profile_id: UUID | None = None) -> BrokerProfile:
        identity = self.brokers.get_profile(profile_id)
        config = self.configs.get(identity.id)
        config = replace(
            config,
            password=self._credentials.get_password(identity.id) or "",
            id=self._runtime_state.get_config_id(identity.id, config.id),
        )
        subscriptions = self.subscriptions.list_for_workspace(identity.workspace_id)
        model = self._runtime_state.get_model(identity.id)
        if model is None:
            model = ObserverModelProcessor.add_topics(
                ObserverModel(root_stats=[]),
                (item.topic_filter for item in subscriptions),
            )
        workspace = ObserverWorkspace(
            id=identity.workspace_id,
            profile_id=identity.id,
            model=model,
            subscriptions=subscriptions,
        )
        return BrokerProfile(
            id=identity.id,
            name=identity.name,
            config=config,
            workspace_id=identity.workspace_id,
            workspace=workspace,
        )

    def get_all_profiles(self) -> tuple[BrokerProfile, ...]:
        return tuple(self.get_profile(item.id) for item in self.brokers.list_profiles())

    def create_profile(self, name: str, config: MqttConfig) -> BrokerProfile:
        name = self.brokers.validate_profile_name(name)
        with self._db.transaction() as session:
            config_id = self.configs.create(config, session=session)
            identity = self.brokers.create_profile(
                name, config_id, session=session
            )
        self._store_password(identity.id, config.password)
        self._runtime_state.set_config_id(identity.id, config.id)
        profile = self.get_profile(identity.id)
        self._runtime_state.set_profile_handle(profile)
        self.save()
        return profile

    def update_profile(self, profile: BrokerProfile) -> None:
        identity = self.brokers.get_profile(profile.id)
        if (
            profile.workspace.profile_id != profile.id
            or profile.workspace_id != identity.workspace_id
            or profile.workspace.id != identity.workspace_id
        ):
            raise ValueError("The workspace must belong to the broker profile.")
        self.brokers.update_profile_name(profile.id, profile.name)
        self.configs.update(profile.id, profile.config)
        self.subscriptions.replace_all(
            identity.workspace_id, profile.workspace.subscriptions
        )
        self._store_password(profile.id, profile.config.password)
        self._runtime_state.set_config_id(profile.id, profile.config.id)
        self._runtime_state.set_profile_handle(profile)
        if identity.is_active:
            self._settings = AppConfig(profile.config, id=self._settings_id)
        self.save()

    def delete_profile(self, profile_id: UUID) -> BrokerProfile:
        profile = self._runtime_state.get_profile_handle(profile_id) or self.get_profile(
            profile_id
        )
        self.brokers.delete_profile(profile_id)
        self._delete_password(profile_id)
        self._runtime_state.remove(profile_id)
        self.save()
        return profile

    def select_active_profile(self, profile_id: UUID) -> None:
        self.brokers.select_active_profile(profile_id)
        self._settings = AppConfig(self.get_profile().config, id=self._settings_id)

    def activate_profile(
        self, profile_id: UUID, config: MqttConfig | None = None
    ) -> None:
        if config is not None:
            self.configs.update(profile_id, config)
            self._store_password(profile_id, config.password)
            self._runtime_state.set_config_id(profile_id, config.id)
        self.select_active_profile(profile_id)

    def replace_subscriptions(self, workspace_id: UUID, subscriptions) -> None:
        self.subscriptions.replace_all(workspace_id, tuple(subscriptions))

    def update_observer_workspace(self, workspace: ObserverWorkspace) -> None:
        self.replace_subscriptions(workspace.id, workspace.subscriptions)

    def update_observer_model(self, model: ObserverModel) -> None:
        self._runtime_state.set_model(self.brokers.get_profile().id, model)
        self.save()

    def get_observer_model(self) -> ObserverModel:
        return self.get_profile().workspace.model

    def get_observer_workspace(self) -> ObserverWorkspace:
        return self.get_profile().workspace

    def get_mqtt(self) -> MqttConfig:
        return self.get_profile().config

    def update_mqtt(self, config: MqttConfig) -> None:
        profile_id = self.brokers.get_profile().id
        self.configs.update(profile_id, config)
        self._store_password(profile_id, config.password)
        self._runtime_state.set_config_id(profile_id, config.id)
        self._settings = AppConfig(config, id=self._settings_id)
        self.save()

    def get(self) -> AppConfig:
        current = self.get_mqtt()
        if self._settings.mqtt != current:
            self._settings = AppConfig(current, id=self._settings_id)
        return self._settings

    def update(self, settings: AppConfig) -> None:
        self.update_mqtt(settings.mqtt)
        self._settings = settings

    def save(self) -> None:
        """Compatibility hook; repositories commit each mutation."""

    def _create_seed_profile(
        self, name: str, config: MqttConfig, *, is_active: bool = False
    ) -> None:
        with self._db.transaction() as session:
            config_id = self.configs.create(config, session=session)
            identity = self.brokers.create_profile(
                name, config_id, is_active=is_active, session=session
            )
        self._store_password(identity.id, config.password)
        self._runtime_state.set_config_id(identity.id, config.id)

    def _store_password(self, profile_id: UUID, password: str) -> None:
        if password:
            self._credentials.set_password(profile_id, password)
        else:
            self._delete_password(profile_id)

    def _delete_password(self, profile_id: UUID) -> None:
        if self._credentials.get_password(profile_id) is not None:
            self._credentials.delete_password(profile_id)
