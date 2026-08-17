from collections.abc import AsyncIterator, Callable
from dataclasses import replace
from uuid import UUID

from topicgate.app.services.service_item import ServiceItem
from topicgate.app.services.observation_cache_service import ObservationCacheService
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.interfaces.broker_profile_store import BrokerProfileStore
from topicgate.core.interfaces.observer_repository import ObserverRepository
from topicgate.core.models.broker_profile import BrokerProfile
from topicgate.core.models.broker_summary import BrokerSummary
from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.core.models.mqtt_observation import MqttObservation
from topicgate.core.models.observation_deletion_preview import (
    ObservationDeletionPreview,
)
from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)
from topicgate.core.models.observer_model import ObserverModel
from topicgate.core.models.subscription import Subscription


class TopicGateRuntime(ServiceItem):
    """Qt-independent application service for broker-backed topic access."""

    def __init__(
        self,
        broker_repository: BrokerProfileStore,
        mqtt_repositories: dict[UUID, ObserverRepository],
        active_broker_id: UUID | None = None,
        mqtt_repository_factory: Callable[
            [BrokerProfile], ObserverRepository
        ] | None = None,
        observation_cache: ObservationCacheService | None = None,
    ) -> None:
        self._brokers = broker_repository
        self._active_broker_id = (
            broker_repository.get_profile().id
            if active_broker_id is None
            else active_broker_id
        )
        self._mqtt_repositories = mqtt_repositories
        self._mqtt_repository_factory = mqtt_repository_factory
        self._observation_cache = observation_cache
        if self._active_broker_id not in self._mqtt_repositories:
            raise ValueError("The active broker requires an MQTT repository.")

    @property
    def active_repo(self) -> ObserverRepository:
        return self._mqtt_repositories[self._active_broker_id]

    async def start(self) -> None:
        await self.active_repo.start()

    async def stop(self) -> None:
        model = self.active_repo.get()
        try:
            await self.active_repo.stop()
        finally:
            self._brokers.update_observer_model(model)

    def list_brokers(self) -> tuple[BrokerSummary, ...]:
        return tuple(
            self._broker_summary(profile)
            for profile in self._brokers.get_all_profiles()
        )

    def list_topics(self) -> tuple[str, ...]:
        return self.active_repo.get_all_topics()

    def get_broker(self, broker_id: UUID | None = None) -> BrokerSummary:
        return self._broker_summary(self._get_broker_profile(broker_id))

    @property
    def active_broker(self) -> BrokerSummary:
        return self.get_broker()

    @property
    def mqtt_config(self) -> MqttConfig:
        return self.active_broker.config

    def get_topic_state(
        self,
        broker_id: UUID,
        topic: str,
    ) -> MqttObservation | None:
        return self._mqtt_repositories[broker_id].get_state(topic)

    def get_observer_model(self, broker_id: UUID) -> ObserverModel:
        return self._mqtt_repositories[broker_id].get()

    def list_subscriptions(self, broker_id: UUID) -> tuple[Subscription, ...]:
        return tuple(self._mqtt_repositories[broker_id].subscriptions)

    def get_retention_policy(self) -> ObservationRetentionPolicy:
        return self._require_observation_cache().get_retention_policy()

    def update_retention_policy(
        self,
        policy: ObservationRetentionPolicy,
    ) -> ObservationRetentionPolicy:
        return self._require_observation_cache().update_retention_policy(policy)

    def preview_clear_cache(
        self,
        broker_id: UUID,
        topics: tuple[str, ...] | None = None,
    ) -> ObservationDeletionPreview:
        self._get_broker_profile(broker_id)
        return self._require_observation_cache().preview_clear_cache(
            broker_id,
            topics,
        )

    def preview_unsubscribed_cache(
        self,
        broker_id: UUID,
    ) -> ObservationDeletionPreview:
        self._get_broker_profile(broker_id)
        return self._require_observation_cache().preview_unsubscribed(
            broker_id,
            self.list_subscriptions(broker_id),
        )

    def confirm_cache_deletion(
        self,
        preview: ObservationDeletionPreview,
    ) -> int:
        self._get_broker_profile(preview.broker_id)
        return self._require_observation_cache().confirm_deletion(preview)

    @property
    def connection_status(self) -> object:
        return self.active_repo.connection_status

    @property
    def dropped_message_count(self) -> int:
        return self.active_repo.dropped_message_count

    @property
    def topic_update_interval(self) -> float:
        return self.active_repo.topic_update_interval

    def messages(self) -> AsyncIterator[MqttMessage]:
        return self.active_repo.messages()

    def drain_pending_messages(self) -> tuple[MqttMessage, ...]:
        return self.active_repo.drain_pending_messages()

    def connection_statuses(self) -> AsyncIterator[object]:
        return self.active_repo.connection_statuses()

    async def connect(self) -> None:
        await self.active_repo.connect()

    async def disconnect(self) -> None:
        await self.active_repo.disconnect()

    async def reconnect(self) -> None:
        await self.active_repo.reconnect()

    def create_broker(self, name: str, mqtt_config: MqttConfig) -> BrokerSummary:
        if self._mqtt_repository_factory is None:
            raise RuntimeError("An observer repository factory is required.")
        profile = self._brokers.create_profile(name, mqtt_config)
        self._mqtt_repositories[profile.id] = self._mqtt_repository_factory(profile)
        return self._broker_summary(profile)

    def update_broker(
        self,
        broker_id: UUID,
        mqtt_config: MqttConfig,
        name: str | None = None,
    ) -> BrokerSummary:
        profile = self._get_broker_profile(broker_id)
        config = self._config_with_stored_password(profile, mqtt_config)
        profile.name = (
            self._validated_profile_name(name, broker_id)
            if name is not None
            else profile.name
        )
        profile.config = config
        self._brokers.update_profile(profile)
        return self.get_broker(broker_id)

    async def activate_broker(
        self,
        broker_id: UUID,
        mqtt_config: MqttConfig | None = None,
        name: str | None = None,
    ) -> BrokerSummary:
        profile = self._get_broker_profile(broker_id)
        config = (
            profile.config
            if mqtt_config is None
            else self._config_with_stored_password(profile, mqtt_config)
        )
        normalized_name = (
            self._validated_profile_name(name, broker_id)
            if name is not None
            else profile.name
        )
        previous_broker_id = self._active_broker_id
        previous_repo = self.active_repo
        selected_repo = self._mqtt_repositories[broker_id]
        switching_repositories = selected_repo is not previous_repo
        if switching_repositories:
            await previous_repo.stop()
        try:
            await selected_repo.update_broker(
                config,
                subscriptions=profile.workspace.subscriptions,
            )
        except Exception:
            if switching_repositories:
                await previous_repo.start()
            raise
        profile.name = normalized_name
        profile.config = config
        self._brokers.update_profile(profile)
        if broker_id != previous_broker_id:
            self._brokers.update_observer_model(previous_repo.get())
        self._brokers.select_active_profile(broker_id)
        if broker_id != previous_broker_id:
            self._active_broker_id = broker_id
        return self.active_broker

    async def delete_broker(self, broker_id: UUID) -> BrokerSummary:
        profile = self._get_broker_profile(broker_id)
        profiles = self.list_brokers()
        if len(profiles) == 1:
            raise ValueError("At least one broker profile is required.")
        if profile.id == self.active_broker.id:
            replacement = next(item for item in profiles if item.id != profile.id)
            await self.activate_broker(replacement.id)
        if self._observation_cache is not None:
            self._observation_cache.flush_pending_writes()
        deleted = self._brokers.delete_profile(profile.id)
        self._mqtt_repositories.pop(profile.id)
        return self._broker_summary(deleted)

    async def add_subscription(
        self,
        broker_id: UUID,
        subscription: Subscription,
    ) -> None:
        self._require_active_broker(broker_id)
        await self.active_repo.add_subscription(subscription)
        self._persist_active_subscriptions()

    async def update_subscription(
        self,
        broker_id: UUID,
        original_filter: str,
        subscription: Subscription,
    ) -> None:
        self._require_active_broker(broker_id)
        await self.active_repo.update_subscription(original_filter, subscription)
        self._persist_active_subscriptions()

    async def remove_subscription(
        self,
        broker_id: UUID,
        subscription: Subscription,
    ) -> None:
        self._require_active_broker(broker_id)
        await self.active_repo.remove_subscription(subscription)
        self._persist_active_subscriptions()

    async def publish(self, broker_id: UUID, topic: str, payload: bytes) -> None:
        self._require_active_broker(broker_id)
        await self.active_repo.publish(topic, payload)

    def _persist_active_subscriptions(self) -> None:
        workspace_id = self._get_broker_profile().workspace_id
        self._brokers.replace_subscriptions(
            workspace_id,
            tuple(self.active_repo.subscriptions),
        )

    def _require_active_broker(self, broker_id: UUID) -> None:
        if broker_id != self.active_broker.id:
            raise ValueError("The operation requires the active broker profile.")

    def _require_observation_cache(self) -> ObservationCacheService:
        if self._observation_cache is None:
            raise RuntimeError("Observation cache operations are unavailable.")
        return self._observation_cache

    def _validated_profile_name(self, name: str, broker_id: UUID) -> str:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("A broker profile name is required.")
        if any(
            profile.id != broker_id
            and profile.name.casefold() == normalized_name.casefold()
            for profile in self.list_brokers()
        ):
            raise ValueError("A broker profile with that name already exists.")
        return normalized_name

    def _get_broker_profile(self, broker_id: UUID | None = None) -> BrokerProfile:
        return self._brokers.get_profile(broker_id)

    @staticmethod
    def _config_with_stored_password(
        profile: BrokerProfile,
        mqtt_config: MqttConfig,
    ) -> MqttConfig:
        if mqtt_config.password or not profile.config.password:
            return mqtt_config
        return replace(mqtt_config, password=profile.config.password)

    @staticmethod
    def _broker_summary(profile: BrokerProfile) -> BrokerSummary:
        config = profile.config
        return BrokerSummary(
            id=profile.id,
            name=profile.name,
            config=MqttConfig(
                host=config.host,
                port=config.port,
                username=config.username,
                password="",
                use_tls=config.use_tls,
                id=config.id,
            ),
            password_configured=bool(config.password),
        )
