from typing import Any, Protocol

from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.infrastructure.mqtt.mqtt_callbacks import MqttCallbacks


class ObserverRepositoryEventSink(Protocol):
    """Repository operations required by the MQTT callback adapter."""

    async def _handle_connected(self) -> None: ...

    def _handle_disconnected(self) -> None: ...

    def handle_message(
        self,
        client: Any,
        userdata: Any,
        message: MqttMessage,
    ) -> None: ...


class ObserverRepositoryCallbacks(MqttCallbacks):
    """Forward MQTT lifecycle events to the owning repository."""

    def __init__(self, repository: ObserverRepositoryEventSink) -> None:
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
