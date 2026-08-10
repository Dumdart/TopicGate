from collections.abc import Callable
from typing import Any

from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.core.models.subscription import Subscription

from ...core.config.mqtt_config import MqttConfig
from .mqtt_callbacks import MqttCallbacks
from .mqtt_client import MqttClient


class MqttGate:
    def __init__(
        self,
        mqtt_config: MqttConfig,
        mqtt_callbacks: MqttCallbacks,
        topic_filters: list[str] | list[Subscription] | None = None,
    ) -> None:
        self.client = MqttClient(mqtt_config)
        self.config = mqtt_config
        self.mqtt_callbacks = mqtt_callbacks
        self._is_started = False
        self._registered_message_filters: list[str] = []

        self.subscriptions = self._build_subscriptions(topic_filters)

    @property
    def topics(self) -> list[str]:
        return [subscription.topic_filter for subscription in self.subscriptions]

    @property
    def dropped_message_count(self) -> int:
        return self.client.dropped_message_count

    def set_subscriptions(self, subscriptions: list[Subscription]) -> None:
        self.subscriptions = list(subscriptions)

    async def start(self, timeout: float = 10.0) -> None:
        self._is_started = await self.client.connect(
            self.callbacks("on_connect", self.mqtt_callbacks),
            timeout=timeout,
            on_disconnect=self.callbacks("on_disconnect", self.mqtt_callbacks),
        )

    async def stop(self) -> None:
        self._is_started = await self.client.disconnect(
            self.callbacks("on_disconnect", self.mqtt_callbacks)
        )

    async def subscribe(
        self, custom_on_message_callback: Callable[..., Any] | None = None
    ) -> int | None:
        # Configure custom callback
        if custom_on_message_callback:
            for topic in self.topics:
                self.client.message_callback_add(topic, custom_on_message_callback)
                self._register_message_filter(topic)

        else:
            for topic in self.topics:
                self.client.message_callback_add(
                    topic,
                    self.callbacks("on_message", self.mqtt_callbacks),
                )
                self._register_message_filter(topic)

        try:
            if len(self.topics) != 0:
                return await self.client.subscribe_multiple(
                    self.subscriptions,
                    self.callbacks("on_subscribe", self.mqtt_callbacks),
                )
        except Exception:
            self._remove_message_callbacks()
            raise

    async def unsubscribe(self) -> int | None:
        try:
            if self.client.is_connected and self.topics:
                return await self.client.unsubscribe_multiple(
                    self.topics,
                    self.callbacks("on_unsubscribe", self.mqtt_callbacks),
                )
        finally:
            self._remove_message_callbacks()

    @property
    def is_started(self) -> bool:
        return self._is_started

    @staticmethod
    def callbacks(event: str, mqtt_callbacks: MqttCallbacks) -> Callable[..., Any]:
        return getattr(mqtt_callbacks, event)

    @staticmethod
    def _build_subscriptions(
        topic_filters: list[str] | list[Subscription] | None = None,
    ) -> list[Subscription]:
        """Return MQTT filters exactly as supplied by the caller.

        Filters are absolute MQTT filters, so a leading or trailing slash and
        wildcard characters are meaningful and must not be normalized.
        """
        if topic_filters is None or len(topic_filters) == 0:
            return []

        return [
            item if isinstance(item, Subscription) else Subscription(item)
            for item in topic_filters
        ]

    def _remove_message_callbacks(self) -> None:
        for topic in self._registered_message_filters:
            self.client.message_callback_remove(topic)
        self._registered_message_filters.clear()

    def _register_message_filter(self, topic: str) -> None:
        if topic not in self._registered_message_filters:
            self._registered_message_filters.append(topic)
