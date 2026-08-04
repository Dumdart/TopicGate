import asyncio
from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Any

from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.interfaces.mqtt_repository import MqttRepository
from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.observer_model import ObserverModel, TopicState
from smart_home_observer.infrastructure.mqtt.mqtt_callbacks import MqttCallbacks
from smart_home_observer.infrastructure.mqtt.mqtt_gate import MqttGate
from smart_home_observer.processors.observer_model_mqtt_message_processor import (
    ObserverModelMqttMessageProcessor,
)
from smart_home_observer.services.observer_model_service import ObserverModelService


class ConnectionStatus(StrEnum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"


class _ObserverRepositoryCallbacks(MqttCallbacks):
    """Forward MQTT lifecycle events to the owning repository."""

    def __init__(self, repository: "ObserverRepository") -> None:
        self._repository = repository

    async def on_connect(
        self,
        client: Any,
        userdata: Any,
        flags: Any,
        rc: Any,
        properties: Any = None,
    ) -> None:
        await self._repository._handle_connected()

    async def on_disconnect(
        self,
        client: Any,
        userdata: Any,
        disconnect_flags: Any,
        reason_code: Any = None,
        properties: Any = None,
    ) -> None:
        self._repository._handle_disconnected()

    async def on_publish(
        self,
        client: Any,
        userdata: Any,
        mid: int,
        reason_code: Any = None,
        properties: Any = None,
    ) -> None:
        return None

    async def on_subscribe(
        self,
        client: Any,
        userdata: Any,
        mid: int,
        granted_qos: Any,
        properties: Any = None,
    ) -> None:
        return None

    async def on_unsubscribe(
        self,
        client: Any,
        userdata: Any,
        mid: int,
        properties: Any = None,
        reason_codes: Any = None,
    ) -> None:
        return None

    async def on_message(self, client: Any, userdata: Any, msg: MqttMessage) -> None:
        self._repository.handle_message(client, userdata, msg)


class ObserverRepository(MqttRepository[ObserverModel]):
    """Observe messages matching the supplied absolute MQTT topic filters."""

    def __init__(self, config: MqttConfig, topic_filters: list[str]) -> None:
        self._state = ObserverModel(root_stats=[])
        self._message_processor = ObserverModelMqttMessageProcessor()
        self.message_queue: asyncio.Queue[MqttMessage] = asyncio.Queue()
        self.connection_status_queue: asyncio.Queue[ConnectionStatus] = asyncio.Queue()
        self.connection_status = ConnectionStatus.DISCONNECTED
        self._is_running = False
        self._is_stopping = False
        self._subscriptions_active = False
        self._subscription_lock = asyncio.Lock()
        self._mqtt_gate = MqttGate(
            config, _ObserverRepositoryCallbacks(self), topic_filters
        )

    async def start(self) -> None:
        if self._is_running:
            return

        self._is_running = True
        self._set_connection_status(ConnectionStatus.CONNECTING)
        try:
            await self._mqtt_gate.start()
            self._set_connection_status(ConnectionStatus.CONNECTED)
            await self._subscribe_once()
        except Exception as ex:
            self._is_running = False
            self._is_stopping = True
            try:
                await self._mqtt_gate.stop()
            except Exception:
                pass
            finally:
                self._is_stopping = False
                self._set_connection_status(ConnectionStatus.DISCONNECTED)
            raise ConnectionError(
                "ObserverRepository could not start the MQTT connection."
            ) from ex

    async def stop(self) -> None:
        if not self._is_running and not self._mqtt_gate.is_started:
            self._set_connection_status(ConnectionStatus.DISCONNECTED)
            return

        self._is_running = False
        self._is_stopping = True
        try:
            try:
                await self._mqtt_gate.unsubscribe()
            finally:
                await self._mqtt_gate.stop()
        except Exception as ex:
            raise ConnectionError(
                "ObserverRepository could not stop the MQTT connection."
            ) from ex
        finally:
            self._is_stopping = False
            self._subscriptions_active = False
            self._set_connection_status(ConnectionStatus.DISCONNECTED)

    def get(self) -> ObserverModel:
        return ObserverModelService.deep_copy(self._state)

    def get_value(self, topic: str) -> bytes | None:
        state = self.get_state(topic)
        return state.payload if state is not None else None

    def get_state(self, topic: str) -> TopicState | None:
        return self._state.topic_states.get(topic)

    def handle_message(
        self, _client: Any, _userdata: Any, msg: MqttMessage
    ) -> None:
        self._message_processor.process(self._state, msg)
        self.message_queue.put_nowait(msg)

    async def messages(self) -> AsyncIterator[MqttMessage]:
        """Yield normalized messages after their current value has been stored."""
        while True:
            yield await self.message_queue.get()

    async def connection_statuses(self) -> AsyncIterator[ConnectionStatus]:
        """Yield future changes to the MQTT connection status."""
        while True:
            yield await self.connection_status_queue.get()

    async def _handle_connected(self) -> None:
        self._set_connection_status(ConnectionStatus.CONNECTED)
        if self._is_running:
            await self._subscribe_once()

    def _handle_disconnected(self) -> None:
        self._subscriptions_active = False
        if self._is_running and not self._is_stopping:
            self._set_connection_status(ConnectionStatus.RECONNECTING)
        else:
            self._set_connection_status(ConnectionStatus.DISCONNECTED)

    async def _subscribe_once(self) -> None:
        async with self._subscription_lock:
            if not self._is_running or self._subscriptions_active:
                return
            await self._mqtt_gate.subscribe(self.handle_message)
            self._subscriptions_active = True

    def _set_connection_status(self, status: ConnectionStatus) -> None:
        if self.connection_status != status:
            self.connection_status = status
            self.connection_status_queue.put_nowait(status)
