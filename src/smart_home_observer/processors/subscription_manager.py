import asyncio
from collections.abc import Callable
from typing import Any

from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.infrastructure.mqtt.mqtt_gate import MqttGate
class SubscriptionManager:
    def __init__(self, mqtt_gate: MqttGate, message_handler: Callable[..., Any]):
        self._mqtt_gate = mqtt_gate
        self._message_handler = message_handler
        self._subscription_lock = asyncio.Lock()
        self._is_running = False
        self._subscriptions_active = False

    async def activate(self) -> None:
        self._is_running = True
        await self.subscribe_once()

    async def deactivate(self) -> None:
        self._subscriptions_active = False
        self._is_running = False
        await self._mqtt_gate.unsubscribe()

    async def add(self, subscription: Subscription) -> None:
        """Add and activate a subscription filter."""
        if any(
            item.topic_filter == subscription.topic_filter
            for item in self._mqtt_gate.subscriptions
        ):
            raise ValueError("That subscription filter already exists.")

        await self._replace_subscriptions(
            [*self._mqtt_gate.subscriptions, subscription]
        )

    async def remove(self, subscription: Subscription) -> None:
        """Remove a subscription filter."""
        if subscription not in self._mqtt_gate.subscriptions:
            raise ValueError("The subscription filter no longer exists.")
        await self._replace_subscriptions(
            [item for item in self._mqtt_gate.subscriptions if item != subscription]
        )

    async def update(self, original_filter: str, subscription: Subscription) -> None:
        """Replace and reactivate one configured subscription filter."""
        index = next(
            (
                index
                for index, item in enumerate(self._mqtt_gate.subscriptions)
                if item.topic_filter == original_filter
            ),
            None,
        )
        if index is None:
            raise ValueError("The subscription filter no longer exists.")
        if any(
            item.topic_filter == subscription.topic_filter
            and item.topic_filter != original_filter
            for item in self._mqtt_gate.subscriptions
        ):
            raise ValueError("That subscription filter already exists.")

        subscriptions = list(self._mqtt_gate.subscriptions)
        subscriptions[index] = subscription
        await self._replace_subscriptions(subscriptions)

    async def subscribe_once(self) -> None:
        async with self._subscription_lock:
            if not self._is_running or self._subscriptions_active:
                return
            await self._mqtt_gate.subscribe(self._message_handler)
            self._subscriptions_active = True

    @property
    def subscriptions(self) -> tuple[Subscription, ...]:
        """Return an immutable snapshot of the configured MQTT filters."""
        return tuple(self._mqtt_gate.subscriptions)

    def disconnect(self) -> None:
        if self._subscriptions_active:
            self._subscriptions_active = False

    async def _replace_subscriptions(self, subscriptions: list[Subscription]) -> None:
        if self._is_running and self._subscriptions_active:
            await self._mqtt_gate.unsubscribe()
            self._subscriptions_active = False
        self._mqtt_gate.set_subscriptions(subscriptions)
        if self._is_running:
            await self.subscribe_once()
