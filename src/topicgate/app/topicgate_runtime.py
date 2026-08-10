from collections.abc import AsyncIterator
from uuid import UUID

from topicgate.app.service_item import ServiceItem
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.broker_profile import BrokerProfile
from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.core.models.observer_model import ObserverModel, TopicState
from topicgate.core.models.subscription import Subscription
from topicgate.infrastructure.repository.broker_repository import BrokerRepository
from topicgate.infrastructure.repository.observer_mqtt_repository import (
    ObserverMqttRepository,
)


class TopicGateRuntime(ServiceItem):
    """Qt-independent application service for broker-backed topic access."""

    def __init__(
        self,
        broker_repository: BrokerRepository,
        mqtt_repository: ObserverMqttRepository,
    ) -> None:
        self._brokers = broker_repository
        self._mqtt = mqtt_repository

    async def start(self) -> None:
        await self._mqtt.start()

    async def stop(self) -> None:
        model = self._mqtt.get()
        try:
            await self._mqtt.stop()
        finally:
            self._brokers.update_observer_model(model)

    def list_brokers(self) -> tuple[BrokerProfile, ...]:
        return self._brokers.get_all_profiles()

    def get_broker(self, broker_id: UUID | None = None) -> BrokerProfile:
        return self._brokers.get_profile(broker_id)

    @property
    def active_broker(self) -> BrokerProfile:
        return self.get_broker()

    @property
    def mqtt_config(self) -> MqttConfig:
        return self.active_broker.config

    def get_topic_state(self, broker_id: UUID, topic: str) -> TopicState | None:
        if broker_id == self.active_broker.id:
            return self._mqtt.get_state(topic)
        return self.get_broker(broker_id).workspace.model.topic_states.get(topic)

    def get_observer_model(self, broker_id: UUID) -> ObserverModel:
        if broker_id == self.active_broker.id:
            return self._mqtt.get()
        return self.get_broker(broker_id).workspace.model

    def list_subscriptions(self, broker_id: UUID) -> tuple[Subscription, ...]:
        if broker_id == self.active_broker.id:
            return tuple(self._mqtt.subscriptions)
        return tuple(self.get_broker(broker_id).workspace.subscriptions)

    @property
    def connection_status(self) -> object:
        return self._mqtt.connection_status

    @property
    def dropped_message_count(self) -> int:
        return self._mqtt.dropped_message_count

    @property
    def topic_update_interval(self) -> float:
        return self._mqtt.topic_update_interval

    def messages(self) -> AsyncIterator[MqttMessage]:
        return self._mqtt.messages()

    def drain_pending_messages(self) -> tuple[MqttMessage, ...]:
        return self._mqtt.drain_pending_messages()

    def connection_statuses(self) -> AsyncIterator[object]:
        return self._mqtt.connection_statuses()

    async def connect(self) -> None:
        await self._mqtt.connect()

    async def disconnect(self) -> None:
        await self._mqtt.disconnect()

    async def reconnect(self) -> None:
        await self._mqtt.reconnect()

    def create_broker(self, name: str, mqtt_config: MqttConfig) -> BrokerProfile:
        mqtt_config.validate_transport_security()
        return self._brokers.create_profile(name, mqtt_config)

    def update_broker(
        self,
        broker_id: UUID,
        mqtt_config: MqttConfig,
        name: str | None = None,
    ) -> BrokerProfile:
        mqtt_config.validate_transport_security()
        profile = self.get_broker(broker_id)
        profile.name = (
            self._validated_profile_name(name, broker_id)
            if name is not None
            else profile.name
        )
        profile.config = mqtt_config
        self._brokers.update_profile(profile)
        return self.get_broker(broker_id)

    async def activate_broker(
        self,
        broker_id: UUID,
        mqtt_config: MqttConfig | None = None,
        name: str | None = None,
    ) -> BrokerProfile:
        profile = self.get_broker(broker_id)
        config = profile.config if mqtt_config is None else mqtt_config
        config.validate_transport_security()
        normalized_name = (
            self._validated_profile_name(name, broker_id)
            if name is not None
            else profile.name
        )
        await self._mqtt.update_broker(
            config,
            profile.workspace.model,
            profile.workspace.subscriptions,
        )
        profile.name = normalized_name
        profile.config = config
        self._brokers.update_profile(profile)
        self._brokers.activate_profile(broker_id, config)
        return self.active_broker

    async def delete_broker(self, broker_id: UUID) -> BrokerProfile:
        profile = self.get_broker(broker_id)
        profiles = self.list_brokers()
        if len(profiles) == 1:
            raise ValueError("At least one broker profile is required.")
        if profile.id == self.active_broker.id:
            replacement = next(item for item in profiles if item.id != profile.id)
            await self.activate_broker(replacement.id)
        return self._brokers.delete_profile(profile.id)

    async def add_subscription(
        self,
        broker_id: UUID,
        subscription: Subscription,
    ) -> None:
        self._require_active_broker(broker_id)
        await self._mqtt.add_subscription(subscription)
        self._persist_active_subscriptions()

    async def update_subscription(
        self,
        broker_id: UUID,
        original_filter: str,
        subscription: Subscription,
    ) -> None:
        self._require_active_broker(broker_id)
        await self._mqtt.update_subscription(original_filter, subscription)
        self._persist_active_subscriptions()

    async def remove_subscription(
        self,
        broker_id: UUID,
        subscription: Subscription,
    ) -> None:
        self._require_active_broker(broker_id)
        await self._mqtt.remove_subscription(subscription)
        self._persist_active_subscriptions()

    async def publish(self, broker_id: UUID, topic: str, payload: bytes) -> None:
        self._require_active_broker(broker_id)
        await self._mqtt.publish(topic, payload)

    def _persist_active_subscriptions(self) -> None:
        workspace = self.active_broker.workspace
        workspace.subscriptions = tuple(self._mqtt.subscriptions)
        self._brokers.update_observer_workspace(workspace)

    def _require_active_broker(self, broker_id: UUID) -> None:
        if broker_id != self.active_broker.id:
            raise ValueError("The operation requires the active broker profile.")

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
