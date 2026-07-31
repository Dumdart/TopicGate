from collections.abc import Callable

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

    def start(self):
        self.client.connect(self.callbacks("on_connect", self.mqtt_callbacks))

    def stop(self):
        self.client.disconnect(self.callbacks("on_disconnect", self.mqtt_callbacks))

    def publish(self, payload, retain: bool = False):
        self.client.publish(
            self.topic,
            payload,
            retain=retain,
            on_publish=self.callbacks("on_publish", self.mqtt_callbacks),
        )

    def subscribe(self):
        self.client.message_callback_add(
            self.topic, self.callbacks("on_message", self.mqtt_callbacks)
        )
        self.client.subscribe(
            self.topic, self.callbacks("on_subscribe", self.mqtt_callbacks)
        )

    def unsubscribe(self):
        self.client.unsubscribe(
            self.topic, self.callbacks("on_unsubscribe", self.mqtt_callbacks)
        )

    def callbacks(self, event: str, mqtt_callbacks: MqttCallbacks) -> Callable:
        return getattr(mqtt_callbacks, event)

    def _build_topic(self, base_topic: str, topic: str | None = None) -> str:
        if topic is None or topic.strip() == "":
            return base_topic

        return f"{base_topic.rstrip('/')}/{topic.strip('/')}"
