import asyncio
import json
from contextlib import suppress
from uuid import UUID

from PySide6.QtCore import QObject, Signal

from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.broker_profile import BrokerProfile
from smart_home_observer.core.models.observer_model import ObserverModel, TopicState
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.gui.broker_state_reader import BrokerStateReader
from smart_home_observer.gui.observer_state_reader import ObserverStateReader
from smart_home_observer.services.observer_model_service import ObserverModelService


def mqtt_filter_matches(topic_filter: str, topic: str) -> bool:
    """Return whether an MQTT topic matches a valid wildcard filter."""
    filter_segments = topic_filter.split("/")
    topic_segments = topic.split("/")

    # Check MQTT's rule that wildcard filters not beginning with '$' do not
    # match system topics.
    if topic.startswith("$") and not topic_filter.startswith("$"):
        return False

    for index, filter_segment in enumerate(filter_segments):
        if filter_segment == "#":
            return index == len(filter_segments) - 1
        if index >= len(topic_segments):
            return False
        if filter_segment != "+" and filter_segment != topic_segments[index]:
            return False

    return len(filter_segments) == len(topic_segments)


class MainViewModel(QObject):
    """Presentation state for the observer workspace."""

    state_changed = Signal()
    topics_changed = Signal()
    subscriptions_changed = Signal()
    connection_changed = Signal()
    configuration_changed = Signal()
    log_message = Signal(str)

    def __init__(
        self,
        repository: ObserverStateReader,
        topic: str = "",
        *,
        broker_repository: BrokerStateReader | None = None,
    ) -> None:
        super().__init__()
        self._repository = repository
        self._broker_repository = broker_repository
        self._topic = topic
        self._state: TopicState | None = None
        self._message_task: asyncio.Task[None] | None = None
        self._connection_task: asyncio.Task[None] | None = None
        self._connection_status = self._status_text(
            getattr(repository, "connection_status", "disconnected")
        )

    @property
    def title(self) -> str:
        return "Smart Home Observer"

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def decoded_payload(self) -> str:
        if self._state is None:
            return "Waiting for a message"
        try:
            decoded = self._state.payload.decode("utf-8")
        except UnicodeDecodeError:
            return "Binary payload (see raw payload below)"

        try:
            return json.dumps(json.loads(decoded), indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            return decoded

    @property
    def value(self) -> str:
        """Backward-compatible alias for the decoded payload."""
        return self.decoded_payload

    @property
    def raw_payload(self) -> str:
        return "-" if self._state is None else self._state.payload.hex(" ")

    @property
    def received_at(self) -> str:
        if self._state is None:
            return "-"
        return self._state.recieved_at.isoformat(timespec="seconds")

    @property
    def quality_of_service(self) -> str:
        return "-" if self._state is None else str(self._state.qos)

    @property
    def retained(self) -> str:
        return "-" if self._state is None else str(self._state.retain)

    @property
    def message_count(self) -> str:
        return "0" if self._state is None else str(self._state.message_count)

    @property
    def connection_status(self) -> str:
        return self._connection_status

    @property
    def mqtt_config(self) -> MqttConfig:
        if self._broker_repository is None:
            raise RuntimeError("MainViewModel requires a broker repository.")
        return self._broker_repository.get_mqtt()

    @property
    def broker_profiles(self) -> tuple[BrokerProfile, ...]:
        if self._broker_repository is None:
            raise RuntimeError("MainViewModel requires a broker repository.")
        return self._broker_repository.get_all_profiles()

    @property
    def active_broker_profile(self) -> BrokerProfile:
        if self._broker_repository is None:
            raise RuntimeError("MainViewModel requires a broker repository.")
        return self._broker_repository.get_profile()

    @property
    def subscriptions(self) -> tuple[Subscription, ...]:
        subscriptions = (
            self.active_broker_profile.workspace.subscriptions
            if self._broker_repository is not None
            and hasattr(self._broker_repository, "update_observer_workspace")
            else getattr(self._repository, "subscriptions", ())
        )
        return tuple(subscriptions)

    @property
    def topic_paths(self) -> list[str]:
        subscriptions = self.subscriptions
        model = self._repository.get()
        paths = {subscription.topic_filter for subscription in subscriptions}
        observed_topics = set(ObserverModelService.get_all_topics(model))
        observed_topics.update(model.topic_states)
        paths.update(
            topic
            for topic in observed_topics
            if any(
                mqtt_filter_matches(subscription.topic_filter, topic)
                for subscription in subscriptions
            )
        )
        return sorted(paths, key=str.casefold)

    @property
    def selected_subscription(self) -> Subscription | None:
        if not self._topic:
            return None
        matches = [
            subscription
            for subscription in self.subscriptions
            if mqtt_filter_matches(subscription.topic_filter, self._topic)
        ]
        if not matches:
            return None
        return max(
            matches,
            key=lambda item: (
                item.topic_filter == self._topic,
                len(item.topic_filter.replace("#", "").replace("+", "")),
            ),
        )

    async def start(self) -> None:
        """Load the current value and listen for messages and connection changes."""
        self.refresh()
        self.topics_changed.emit()
        self.connection_changed.emit()
        if self._message_task is None:
            self._message_task = asyncio.create_task(self._observe_messages())
        if (
            self._connection_task is None
            and hasattr(self._repository, "connection_statuses")
        ):
            self._connection_task = asyncio.create_task(
                self._observe_connection_statuses()
            )

    async def stop(self) -> None:
        """Stop listening for repository events."""
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

    def select_topic(self, topic: str) -> None:
        if topic == self._topic:
            return
        self._topic = topic
        self.refresh()
        self.subscriptions_changed.emit()

    def refresh(self) -> None:
        self._state = self._repository.get_state(self._topic) if self._topic else None
        self.state_changed.emit()

    async def add_subscription(self, subscription: Subscription) -> None:
        await self._repository.add_subscription(subscription)
        self._store_active_profile_subscriptions()
        self.log_message.emit(f"Added subscription: {subscription.topic_filter}")
        self.topics_changed.emit()
        self.subscriptions_changed.emit()

    async def remove_subscription(self, subscription: Subscription) -> None:
        await self._repository.remove_subscription(subscription)
        self._store_active_profile_subscriptions()
        self.log_message.emit(f"Removed subscription: {subscription.topic_filter}")
        if self._topic not in self.topic_paths:
            self._topic = ""
            self.refresh()
        self.topics_changed.emit()
        self.subscriptions_changed.emit()

    async def update_subscription(
        self, original_filter: str, subscription: Subscription
    ) -> None:
        await self._repository.update_subscription(original_filter, subscription)
        self._store_active_profile_subscriptions()
        self.log_message.emit(
            f"Updated subscription: {original_filter} -> {subscription.topic_filter}"
        )
        if self._topic == original_filter:
            self._topic = subscription.topic_filter
            self.refresh()
        self.topics_changed.emit()
        self.subscriptions_changed.emit()

    async def reconnect_to_broker(self) -> None:
        self.log_message.emit("Reconnect requested")
        await self._repository.reconnect()

    async def connect_to_broker(self) -> None:
        self.log_message.emit("Connect requested")
        await self._repository.connect()


    async def disconnect_from_broker(self) -> None:
        self.log_message.emit("Disconnect requested")
        await self._repository.disconnect()

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
        if self._broker_repository is None:
            raise RuntimeError("MainViewModel requires a broker repository.")

        profile = self._broker_repository.get_profile(profile_id)
        profile_changed = profile.id != self.active_broker_profile.id
        normalized_name = (
            self._validated_profile_name(profile_name, profile_id)
            if profile_name is not None
            else profile.name
        )

        self.log_message.emit(
            f"Connecting to MQTT broker: {mqtt_config.host}:{mqtt_config.port}"
        )
        try:
            await self._repository.update_broker(
                mqtt_config,
                profile.workspace.model,
                profile.workspace.subscriptions,
            )
        except Exception as error:
            self.log_message.emit(f"Broker update failed: {error}")
            raise
        self._persist_broker_profile(profile_id, mqtt_config, normalized_name)
        self._broker_repository.activate_profile(profile_id, mqtt_config)
        if profile_changed:
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
    ) -> BrokerProfile:
        """Persist broker settings without changing the MQTT connection."""
        if self._broker_repository is None:
            raise RuntimeError("MainViewModel requires a broker repository.")

        profile = self._persist_broker_profile(
            profile_id,
            mqtt_config,
            profile_name,
        )
        self.configuration_changed.emit()
        self.log_message.emit(f"Saved broker profile: {profile.name}")
        return profile

    def _persist_broker_profile(
        self,
        profile_id: UUID,
        mqtt_config: MqttConfig,
        profile_name: str | None,
    ) -> BrokerProfile:
        if self._broker_repository is None:
            raise RuntimeError("MainViewModel requires a broker repository.")
        profile = self._broker_repository.get_profile(profile_id)
        profile.name = (
            self._validated_profile_name(profile_name, profile_id)
            if profile_name is not None
            else profile.name
        )
        profile.config = mqtt_config
        self._broker_repository.update_profile(profile)
        return self._broker_repository.get_profile(profile_id)

    def create_broker_profile(
        self,
        name: str,
        mqtt_config: MqttConfig,
    ) -> BrokerProfile:
        """Create a selectable broker profile without changing connections."""
        if self._broker_repository is None:
            raise RuntimeError("MainViewModel requires a broker repository.")
        profile = self._broker_repository.create_profile(name, mqtt_config)
        self.configuration_changed.emit()
        self.log_message.emit(f"Created broker profile: {profile.name}")
        return profile

    async def delete_broker_profile(self, profile_id: UUID) -> None:
        """Delete a profile, switching away first when it is active."""
        if self._broker_repository is None:
            raise RuntimeError("MainViewModel requires a broker repository.")
        profile = self._broker_repository.get_profile(profile_id)
        profiles = self.broker_profiles
        if len(profiles) == 1:
            raise ValueError("At least one broker profile is required.")
        if profile.id == self.active_broker_profile.id:
            replacement = next(item for item in profiles if item.id != profile.id)
            await self.update_broker_profile(replacement.id, replacement.config)
        self._broker_repository.delete_profile(profile.id)
        self.configuration_changed.emit()
        self.log_message.emit(f"Deleted broker profile: {profile.name}")

    def _store_active_profile_subscriptions(self) -> None:
        """Persist the active broker's subscriptions with its workspace."""
        if self._broker_repository is None:
            return

        workspace = self.active_broker_profile.workspace
        workspace.subscriptions = tuple(
            getattr(self._repository, "subscriptions", ())
        )
        update_workspace = getattr(
            self._broker_repository,
            "update_observer_workspace",
            None,
        )
        if update_workspace is not None:
            update_workspace(workspace)

    def _validated_profile_name(self, name: str, profile_id: UUID) -> str:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("A broker profile name is required.")
        if any(
            profile.id != profile_id
            and profile.name.casefold() == normalized_name.casefold()
            for profile in self.broker_profiles
        ):
            raise ValueError("A broker profile with that name already exists.")
        return normalized_name

    async def _observe_messages(self) -> None:
        async for message in self._repository.messages():
            self.log_message.emit(
                f"Received {message.topic} (QoS {message.qos}, "
                f"retained {'yes' if message.retain else 'no'})"
            )
            self.topics_changed.emit()
            if message.topic == self._topic:
                self.refresh()

    async def _observe_connection_statuses(self) -> None:
        async for status in self._repository.connection_statuses():
            self._connection_status = self._status_text(status)
            self.connection_changed.emit()
            self.log_message.emit(f"Connection {self._connection_status}")

    @staticmethod
    def _status_text(status: object) -> str:
        value = getattr(status, "value", status)
        return str(value).lower()
