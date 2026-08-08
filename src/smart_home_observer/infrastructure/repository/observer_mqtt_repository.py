import asyncio
from collections.abc import AsyncIterator
from typing import Any

from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.interfaces.mqtt_repository import MqttRepository
from smart_home_observer.core.models.connection_status import ConnectionStatus
from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.observer_model import ObserverModel, TopicState
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.infrastructure.mqtt.callbacks.observer_repository_callbacks import (
    ObserverRepositoryCallbacks,
)
from smart_home_observer.infrastructure.mqtt.mqtt_gate import MqttGate
from smart_home_observer.processors.observer_model_mqtt_message_processor import (
    ObserverModelMqttMessageProcessor,
)
from smart_home_observer.processors.subscription_manager import SubscriptionManager
from smart_home_observer.services.observer_model_service import ObserverModelService


class ObserverMqttRepository(MqttRepository[ObserverModel]):
    """Observe messages matching the supplied absolute MQTT topic filters."""

    def __init__(
        self,
        config: MqttConfig,
        topic_filters: list[str] | list[Subscription],
        model: ObserverModel | None = None,
    ) -> None:
        self._state = model if model is not None else ObserverModel(root_stats=[])
        self._message_processor = ObserverModelMqttMessageProcessor()
        self.message_queue: asyncio.Queue[MqttMessage] = asyncio.Queue()
        self.connection_status_queue: asyncio.Queue[ConnectionStatus] = asyncio.Queue()
        self.connection_status = ConnectionStatus.DISCONNECTED
        self._is_running = False
        self._is_stopping = False
        self._lifecycle_lock = asyncio.Lock()
        self._mqtt_gate = MqttGate(
            config, ObserverRepositoryCallbacks(self), topic_filters
        )
        self._subscription_manager = SubscriptionManager(
            self._mqtt_gate, self.handle_message
        )

    async def start(self) -> None:
        async with self._lifecycle_lock:
            await self._start()

    async def _start(self) -> None:
        if self._is_running:
            return

        self._is_running = True
        self._set_connection_status(ConnectionStatus.CONNECTING)
        try:
            await self._mqtt_gate.start()
            self._set_connection_status(ConnectionStatus.CONNECTED)
            await self._subscription_manager.activate()
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
                f"ObserverRepository could not start the MQTT connection: {ex}"
            ) from ex

    async def stop(self) -> None:
        async with self._lifecycle_lock:
            await self._stop()

    async def _stop(self) -> None:
        if not self._is_running and not self._mqtt_gate.is_started:
            self._set_connection_status(ConnectionStatus.DISCONNECTED)
            return

        self._is_running = False
        self._is_stopping = True
        try:
            try:
                await self._subscription_manager.deactivate()
            finally:
                await self._mqtt_gate.stop()
        except Exception as ex:
            raise ConnectionError(
                "ObserverRepository could not stop the MQTT connection."
            ) from ex
        finally:
            self._is_stopping = False
            self._set_connection_status(ConnectionStatus.DISCONNECTED)

    async def update_broker(
        self,
        new_config: MqttConfig,
        model: ObserverModel | None = None,
        subscriptions: tuple[Subscription, ...] | None = None,
    ) -> None:
        """Replace the MQTT connection with one configured for a new broker."""
        async with self._lifecycle_lock:
            previous_gate = self._mqtt_gate
            previous_manager = self._subscription_manager
            previous_model = self._state
            was_running = self._is_running
            active_subscriptions = list(
                self.subscriptions if subscriptions is None else subscriptions
            )

            if was_running or self._mqtt_gate.is_started:
                await self._stop()

            self._mqtt_gate = MqttGate(
                new_config,
                ObserverRepositoryCallbacks(self),
                active_subscriptions,
            )
            self._subscription_manager = SubscriptionManager(
                self._mqtt_gate, self.handle_message
            )
            if model is not None:
                self._state = model

            try:
                await self._start()
            except Exception:
                # Check that a failed broker change leaves the repository using
                # the previous, known configuration rather than the failed one.
                self._mqtt_gate = previous_gate
                self._subscription_manager = previous_manager
                self._state = previous_model
                if was_running:
                    try:
                        await self._start()
                    except Exception:
                        pass
                raise

    def get(self) -> ObserverModel:
        return ObserverModelService.deep_copy(self._state)

    def get_value(self, topic: str) -> bytes | None:
        state = self.get_state(topic)
        return state.payload if state is not None else None

    def get_state(self, topic: str) -> TopicState | None:
        return self._state.topic_states.get(topic)

    def handle_message(self, _client: Any, _userdata: Any, msg: MqttMessage) -> None:
        self._message_processor.process(self._state, msg)
        self.message_queue.put_nowait(msg)

    @property
    def subscriptions(self) -> tuple[Subscription, ...]:
        return self._subscription_manager.subscriptions

    async def add_subscription(self, subscription: Subscription) -> None:
        async with self._lifecycle_lock:
            await self._subscription_manager.add(subscription)

    async def remove_subscription(self, subscription: Subscription) -> None:
        async with self._lifecycle_lock:
            await self._subscription_manager.remove(subscription)

    async def update_subscription(
        self,
        original_filter: str,
        subscription: Subscription,
    ) -> None:
        async with self._lifecycle_lock:
            await self._subscription_manager.update(original_filter, subscription)

    async def reconnect(self) -> None:
        """Reconnect and restore all active subscriptions."""
        async with self._lifecycle_lock:
            await self._stop()
            await self._start()

    async def disconnect(self) -> None:
        """Disconnect from MQTT while preserving configured subscriptions."""
        await self.stop()

    async def connect(self) -> None:
        """Connect to MQTT and activate all configured subscriptions."""
        await self.start()

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
            await self._subscription_manager.subscribe_once()

    def _handle_disconnected(self) -> None:
        self._subscription_manager.disconnect()

        if self._is_running and not self._is_stopping:
            self._set_connection_status(ConnectionStatus.RECONNECTING)
        else:
            self._set_connection_status(ConnectionStatus.DISCONNECTED)

    def _set_connection_status(self, status: ConnectionStatus) -> None:
        if self.connection_status != status:
            self.connection_status = status
            self.connection_status_queue.put_nowait(status)
