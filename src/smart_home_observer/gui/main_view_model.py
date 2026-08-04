import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Protocol

from PySide6.QtCore import QObject, Signal

from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.observer_model import TopicState


class ObserverStateReader(Protocol):
    """Provides the current state and future MQTT messages for the observer UI."""

    def get_state(self, topic: str) -> TopicState | None:
        """Return the latest state for a topic, if one has been received."""

    def messages(self) -> AsyncIterator[MqttMessage]:
        """Yield received MQTT messages."""


class MainViewModel(QObject):
    """Presentation state for the currently displayed observer topic."""

    state_changed = Signal()

    def __init__(self, repository: ObserverStateReader, topic: str) -> None:
        super().__init__()
        self._repository = repository
        self._topic = topic
        self._state: TopicState | None = None
        self._message_task: asyncio.Task[None] | None = None

    @property
    def title(self) -> str:
        return "Smart Home Observer"

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def value(self) -> str:
        if self._state is None:
            return "Waiting for a message"

        try:
            return self._state.payload.decode("utf-8")
        except UnicodeDecodeError:
            return self._state.payload.hex(" ")

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

    async def start(self) -> None:
        """Load the current value and listen for later updates."""
        self.refresh()
        if self._message_task is None:
            self._message_task = asyncio.create_task(self._observe_messages())

    async def stop(self) -> None:
        """Stop listening for MQTT messages."""
        if self._message_task is None:
            return

        self._message_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._message_task
        self._message_task = None

    def refresh(self) -> None:
        """Refresh the presentation state from the repository snapshot."""
        self._state = self._repository.get_state(self._topic)
        self.state_changed.emit()

    async def _observe_messages(self) -> None:
        async for message in self._repository.messages():
            if message.topic == self._topic:
                self.refresh()
