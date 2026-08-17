import asyncio
import binascii
from base64 import b64decode
from contextlib import asynccontextmanager
from contextlib import suppress
from typing import AsyncIterator
from uuid import UUID

from PySide6.QtCore import QObject, Signal

from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.broker_summary import BrokerSummary
from topicgate.core.models.mqtt_observation import MqttObservation
from topicgate.core.models.observer_model import ObserverModel
from topicgate.core.models.subscription import Subscription
from topicgate.core.mqtt_topics import mqtt_filter_matches
from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.presentation.topic_presentation import (
    TopicDetail,
    TopicTreeNode,
    build_topic_tree,
    collect_visible_topic_paths,
    matching_subscription,
    topic_detail,
)
from topicgate.processors.observer_model_processor import ObserverModelProcessor


class MainViewModel(QObject):
    """Presentation state for the observer workspace."""

    state_changed = Signal()
    topics_changed = Signal()
    subscriptions_changed = Signal()
    connection_changed = Signal()
    configuration_changed = Signal()
    log_message = Signal(str)
    operation_state_changed = Signal()
    operation_failed = Signal(str, str)

    def __init__(
        self,
        runtime: TopicGateRuntime,
        topic: str = "",
    ) -> None:
        super().__init__()
        self._runtime = runtime
        self._topic = topic
        self._state: MqttObservation | None = None
        self._message_task: asyncio.Task[None] | None = None
        self._connection_task: asyncio.Task[None] | None = None
        self._connection_status = self._status_text(
            runtime.connection_status
        )
        self._reported_dropped_messages = 0
        self._busy_operations: set[str] = set()

    @property
    def title(self) -> str:
        return "TopicGate Desktop"

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def decoded_payload(self) -> str:
        return self.topic_detail.decoded_payload

    @property
    def value(self) -> str:
        """Backward-compatible alias for the decoded payload."""
        return self.decoded_payload

    @property
    def raw_payload(self) -> str:
        return self.topic_detail.raw_payload

    @property
    def topic_detail(self) -> TopicDetail:
        return topic_detail(
            self._state,
            self._topic,
            self._runtime.dropped_message_count,
        )

    @property
    def received_at(self) -> str:
        return self.topic_detail.received_at

    @property
    def quality_of_service(self) -> str:
        return self.topic_detail.qos_label

    @property
    def retained(self) -> str:
        return "-" if self._state is None else str(self._state.retain)

    @property
    def message_count(self) -> str:
        return str(self.topic_detail.message_count)

    @property
    def dropped_message_count(self) -> str:
        return str(self._runtime.dropped_message_count)

    @property
    def connection_status(self) -> str:
        return self._connection_status

    def is_busy(self, operation: str) -> bool:
        return operation in self._busy_operations

    @property
    def any_operation_busy(self) -> bool:
        return bool(self._busy_operations)

    @property
    def mqtt_config(self) -> MqttConfig:
        return self._runtime.mqtt_config

    @property
    def broker_profiles(self) -> tuple[BrokerSummary, ...]:
        return self._runtime.list_brokers()

    @property
    def active_broker_profile(self) -> BrokerSummary:
        return self._runtime.active_broker

    @property
    def subscriptions(self) -> tuple[Subscription, ...]:
        return self._runtime.list_subscriptions(self.active_broker_profile.id)

    @property
    def topic_paths(self) -> list[str]:
        subscriptions = self.subscriptions
        model = self._runtime.get_observer_model(self.active_broker_profile.id)
        observed_topics = set(ObserverModelProcessor.get_all_topics(model))
        observed_topics.update(model.topic_states)
        return list(collect_visible_topic_paths(subscriptions, observed_topics))

    @property
    def topic_tree(self) -> tuple[TopicTreeNode, ...]:
        model = self._runtime.get_observer_model(self.active_broker_profile.id)
        observed_topics = set(ObserverModelProcessor.get_all_topics(model))
        observed_topics.update(model.topic_states)
        return build_topic_tree(
            self.topic_paths,
            self.subscriptions,
            observed_topics,
        )

    @property
    def selected_subscription(self) -> Subscription | None:
        return matching_subscription(self.subscriptions, self._topic)

    async def start(self) -> None:
        """Load the current value and listen for messages and connection changes."""
        self.refresh()
        self.topics_changed.emit()
        self.connection_changed.emit()
        if self._message_task is None:
            self._message_task = asyncio.create_task(self._observe_messages())
        if self._connection_task is None:
            self._connection_task = asyncio.create_task(
                self._observe_connection_statuses()
            )

    async def stop(self) -> None:
        """Stop listening for repository events."""
        await self._cancel_observer_tasks()

    async def _cancel_observer_tasks(self) -> None:
        tasks = [
            task
            for task in (self._message_task, self._connection_task)
            if task is not None
        ]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        self._message_task = None
        self._connection_task = None

    async def _restart_observer_tasks(self) -> None:
        observe_messages = self._message_task is not None
        observe_connections = self._connection_task is not None
        await self._cancel_observer_tasks()
        if observe_messages:
            self._message_task = asyncio.create_task(self._observe_messages())
        if observe_connections:
            self._connection_task = asyncio.create_task(
                self._observe_connection_statuses()
            )

    def select_topic(self, topic: str) -> None:
        if topic == self._topic:
            return
        self._topic = topic
        self.refresh()
        self.subscriptions_changed.emit()

    def refresh(self) -> None:
        self._state = (
            self._runtime.get_topic_state(
                self.active_broker_profile.id,
                self._topic,
            )
            if self._topic
            else None
        )
        self.state_changed.emit()

    async def add_subscription(self, subscription: Subscription) -> None:
        async with self._operation("subscription"):
            await self._runtime.add_subscription(
                self.active_broker_profile.id,
                subscription,
            )
            self.log_message.emit(f"Added subscription: {subscription.topic_filter}")
            self.topics_changed.emit()
            self.subscriptions_changed.emit()

    async def remove_subscription(self, subscription: Subscription) -> None:
        async with self._operation("subscription"):
            await self._runtime.remove_subscription(
                self.active_broker_profile.id,
                subscription,
            )
            self.log_message.emit(f"Removed subscription: {subscription.topic_filter}")
            if self._topic not in self.topic_paths:
                self._topic = ""
                self.refresh()
            self.topics_changed.emit()
            self.subscriptions_changed.emit()

    async def update_subscription(
        self, original_filter: str, subscription: Subscription
    ) -> None:
        async with self._operation("subscription"):
            await self._runtime.update_subscription(
                self.active_broker_profile.id,
                original_filter,
                subscription,
            )
            self.log_message.emit(
                f"Updated subscription: {original_filter} -> {subscription.topic_filter}"
            )
            if self._topic == original_filter:
                self._topic = subscription.topic_filter
                self.refresh()
            self.topics_changed.emit()
            self.subscriptions_changed.emit()

    async def reconnect_to_broker(self) -> None:
        async with self._operation("connection"):
            self.log_message.emit("Reconnect requested")
            await self._runtime.reconnect()

    async def connect_to_broker(self) -> None:
        async with self._operation("connection"):
            self.log_message.emit("Connect requested")
            await self._runtime.connect()


    async def disconnect_from_broker(self) -> None:
        async with self._operation("connection"):
            self.log_message.emit("Disconnect requested")
            await self._runtime.disconnect()

    async def update_mqtt_config(self, mqtt_config: MqttConfig) -> None:
        """Apply broker settings before retaining them in application settings."""
        await self.update_broker_profile(
            self.active_broker_profile.id,
            mqtt_config,
        )

    async def update_broker_profile(
        self,
        profile_id: UUID,
        mqtt_config: MqttConfig,
        profile_name: str | None = None,
    ) -> None:
        """Backward-compatible alias for activating a broker profile."""
        await self.activate_broker_profile(
            profile_id,
            mqtt_config,
            profile_name,
        )

    async def activate_broker_profile(
        self,
        profile_id: UUID,
        mqtt_config: MqttConfig,
        profile_name: str | None = None,
    ) -> None:
        """Connect with a profile and make it active only after success."""
        async with self._operation("broker"):
            profile = self._runtime.get_broker(profile_id)
            profile_changed = profile.id != self.active_broker_profile.id
            self.log_message.emit(
                f"Connecting to MQTT broker: {mqtt_config.host}:{mqtt_config.port}"
            )
            try:
                await self._runtime.activate_broker(
                    profile_id,
                    mqtt_config,
                    profile_name,
                )
            except Exception as error:
                self.log_message.emit(f"Broker update failed: {error}")
                raise
            if profile_changed:
                await self._restart_observer_tasks()
                self._topic = ""
                self.refresh()
                self.topics_changed.emit()
                self.subscriptions_changed.emit()
            self.configuration_changed.emit()
            self.log_message.emit(
                f"Updated MQTT broker: {mqtt_config.host}:{mqtt_config.port}"
            )

    def save_broker_profile(
        self,
        profile_id: UUID,
        mqtt_config: MqttConfig,
        profile_name: str | None = None,
    ) -> BrokerSummary:
        """Persist broker settings without changing the MQTT connection."""
        profile = self._runtime.update_broker(
            profile_id,
            mqtt_config,
            profile_name,
        )
        self.configuration_changed.emit()
        self.log_message.emit(f"Saved broker profile: {profile.name}")
        return profile

    def create_broker_profile(
        self,
        name: str,
        mqtt_config: MqttConfig,
    ) -> BrokerSummary:
        """Create a selectable broker profile without changing connections."""
        profile = self._runtime.create_broker(name, mqtt_config)
        self.configuration_changed.emit()
        self.log_message.emit(f"Created broker profile: {profile.name}")
        return profile

    async def delete_broker_profile(self, profile_id: UUID) -> None:
        """Delete a profile, switching away first when it is active."""
        profile = self._runtime.get_broker(profile_id)
        active_profile_id = self.active_broker_profile.id
        replacement = next(
            (
                item
                for item in self.broker_profiles
                if item.id != profile_id
            ),
            None,
        )
        if active_profile_id == profile_id and replacement is not None:
            self.log_message.emit(
                "Connecting to MQTT broker: "
                f"{replacement.config.host}:{replacement.config.port}"
            )
        async with self._operation("broker"):
            await self._runtime.delete_broker(profile_id)
            if active_profile_id == profile_id:
                self._topic = ""
                self.refresh()
                self.topics_changed.emit()
                self.subscriptions_changed.emit()
                self.configuration_changed.emit()
                active = self.active_broker_profile
                self.log_message.emit(
                    f"Updated MQTT broker: {active.config.host}:{active.config.port}"
                )
            self.configuration_changed.emit()
            self.log_message.emit(f"Deleted broker profile: {profile.name}")

    async def publish_message(
        self,
        topic: str,
        payload: str,
        encoding: str = "utf-8",
    ) -> None:
        topic = topic.strip()
        if not topic:
            raise ValueError("A publish topic is required.")
        if encoding == "utf-8":
            payload_bytes = payload.encode("utf-8")
        elif encoding == "base64":
            try:
                payload_bytes = b64decode(payload, validate=True)
            except (binascii.Error, ValueError) as error:
                raise ValueError("Payload is not valid base64.") from error
        else:
            raise ValueError("Encoding must be UTF-8 or base64.")
        async with self._operation("publish"):
            await self._runtime.publish(
                self.active_broker_profile.id,
                topic,
                payload_bytes,
            )
            self.log_message.emit(f"Published message: {topic}")

    def report_operation_error(self, title: str, error: BaseException) -> None:
        message = str(error)
        self.log_message.emit(f"{title}: {message}")
        self.operation_failed.emit(title, message)

    @asynccontextmanager
    async def _operation(self, name: str) -> AsyncIterator[None]:
        if name in self._busy_operations:
            raise RuntimeError(f"The {name} operation is already in progress.")
        self._busy_operations.add(name)
        self.operation_state_changed.emit()
        try:
            yield
        finally:
            self._busy_operations.discard(name)
            self.operation_state_changed.emit()

    async def _observe_messages(self) -> None:
        async for message in self._runtime.messages():
            update_interval = float(self._runtime.topic_update_interval)
            if update_interval > 0:
                await asyncio.sleep(update_interval)
            messages = (message,)
            messages += self._runtime.drain_pending_messages()

            latest = messages[-1]
            if len(messages) == 1:
                self.log_message.emit(
                    f"Received {latest.topic} (QoS {latest.qos}, "
                    f"retained {'yes' if latest.retain else 'no'})"
                )
            else:
                self.log_message.emit(
                    f"Received {len(messages)} MQTT messages "
                    f"(latest: {latest.topic})"
                )

            dropped = int(self.dropped_message_count)
            if dropped > self._reported_dropped_messages:
                newly_dropped = dropped - self._reported_dropped_messages
                self.log_message.emit(
                    f"Dropped {newly_dropped} MQTT messages during admission "
                    f"({dropped} total)"
                )
                self._reported_dropped_messages = dropped

            self.topics_changed.emit()
            if any(item.topic == self._topic for item in messages):
                self.refresh()

    async def _observe_connection_statuses(self) -> None:
        async for status in self._runtime.connection_statuses():
            self._connection_status = self._status_text(status)
            self.connection_changed.emit()
            self.log_message.emit(f"Connection {self._connection_status}")

    @staticmethod
    def _status_text(status: object) -> str:
        value = getattr(status, "value", status)
        return str(value).lower()
