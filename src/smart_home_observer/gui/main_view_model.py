import asyncio
import json
from contextlib import suppress

from PySide6.QtCore import QObject, Signal

from smart_home_observer.core.models.observer_model import TopicState
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.gui.observer_state_reader import ObserverStateReader


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
    log_message = Signal(str)

    def __init__(self, repository: ObserverStateReader, topic: str = "") -> None:
        super().__init__()
        self._repository = repository
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
    def subscriptions(self) -> tuple[Subscription, ...]:
        subscriptions = getattr(self._repository, "subscriptions", ())
        return tuple(subscriptions)

    @property
    def topic_paths(self) -> list[str]:
        paths = {subscription.topic_filter for subscription in self.subscriptions}
        get_snapshot = getattr(self._repository, "get", None)
        if get_snapshot is not None:
            paths.update(get_snapshot().topic_states)
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
        self.log_message.emit(f"Added subscription: {subscription.topic_filter}")
        self.topics_changed.emit()
        self.subscriptions_changed.emit()

    async def remove_suscrioption(
        self, subscription: Subscription
    ) -> None:
        # await self._repository.remove_subscription(subscription)
        self.log_message.emit(f"Removed subscription: {subscription.topic_filter}")
        self.topics_changed.emit()
        self.subscriptions_changed.emit()

    async def update_subscription(
        self, original_filter: str, subscription: Subscription
    ) -> None:
        await self._repository.update_subscription(original_filter, subscription)
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
