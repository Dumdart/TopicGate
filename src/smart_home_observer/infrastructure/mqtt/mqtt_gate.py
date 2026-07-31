from collections.abc import Callable
from typing import Any

from ...core.config.mqtt_config import MqttConfig
from .mqtt_callbacks import MqttCallbacks
from .mqtt_client import MqttClient


class MqttGate:
    def __init__(
        self,
        mqtt_config: MqttConfig,
        mqtt_callbacks: MqttCallbacks,
        topic: str | None = None,
    ):
        self.client = MqttClient(mqtt_config)
        self.config = mqtt_config
        self.mqtt_callbacks = mqtt_callbacks
        self.topic = self._build_topic(mqtt_config.base_topic, topic)

    async def start(self, timeout: float = 10.0) -> None:
        await self.client.connect(
            self.callbacks("on_connect", self.mqtt_callbacks), timeout=timeout
        )

    async def stop(self) -> None:
        await self.client.disconnect(
            self.callbacks("on_disconnect", self.mqtt_callbacks)
        )

    async def publish(self, payload: Any, retain: bool = False) -> int:
        return await self.client.publish(
            self.topic,
            payload,
            retain=retain,
            on_publish=self.callbacks("on_publish", self.mqtt_callbacks),
        )

    async def subscribe(self) -> int:
        self.client.message_callback_add(
            self.topic,
            self.callbacks("on_message", self.mqtt_callbacks),
        )
        return await self.client.subscribe(
            self.topic,
            self.callbacks("on_subscribe", self.mqtt_callbacks),
        )

    async def unsubscribe(self) -> int:
        return await self.client.unsubscribe(
            self.topic,
            self.callbacks("on_unsubscribe", self.mqtt_callbacks),
        )

    @staticmethod
    def callbacks(event: str, mqtt_callbacks: MqttCallbacks) -> Callable[..., Any]:
        return getattr(mqtt_callbacks, event)

    @staticmethod
    def _build_topic(base_topic: str, topic: str | None = None) -> str:
        if topic is None or topic.strip() == "":
            return base_topic

        return f"{base_topic.rstrip('/')}/{topic.strip('/')}"
