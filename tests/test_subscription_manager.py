import asyncio
from unittest.mock import AsyncMock, MagicMock

from topicgate.core.models.subscription import Subscription
from topicgate.processors.subscription_manager import SubscriptionManager


def build_manager(
    subscriptions: list[Subscription] | None = None,
) -> tuple[SubscriptionManager, MagicMock, MagicMock]:
    mqtt_gate = MagicMock()
    mqtt_gate.subscriptions = list(subscriptions or [])
    mqtt_gate.subscribe = AsyncMock()
    mqtt_gate.unsubscribe = AsyncMock()

    def set_subscriptions(items: list[Subscription]) -> None:
        mqtt_gate.subscriptions = list(items)

    mqtt_gate.set_subscriptions.side_effect = set_subscriptions
    message_handler = MagicMock()
    return SubscriptionManager(mqtt_gate, message_handler), mqtt_gate, message_handler


async def test_subscribe_once_before_activation_does_nothing() -> None:
    async def scenario() -> None:
        manager, mqtt_gate, _ = build_manager()

        await manager.subscribe_once()

        mqtt_gate.subscribe.assert_not_awaited()

    await scenario()


async def test_activation_subscribes_once_with_the_configured_message_handler() -> None:
    async def scenario() -> None:
        manager, mqtt_gate, message_handler = build_manager()

        await manager.activate()
        await manager.subscribe_once()

        mqtt_gate.subscribe.assert_awaited_once_with(message_handler)

    await scenario()


async def test_deactivation_unsubscribes_and_prevents_changes_from_subscribing() -> None:
    async def scenario() -> None:
        original = Subscription("SmartHome/old/#")
        added = Subscription("SmartHome/new/#")
        manager, mqtt_gate, _ = build_manager([original])
        await manager.activate()

        await manager.deactivate()
        await manager.add(added)

        mqtt_gate.unsubscribe.assert_awaited_once()
        mqtt_gate.subscribe.assert_awaited_once()
        assert manager.subscriptions == (original, added)

    await scenario()


async def test_disconnect_allows_subscriptions_to_be_restored() -> None:
    async def scenario() -> None:
        manager, mqtt_gate, _ = build_manager()
        await manager.activate()

        manager.disconnect()
        await manager.subscribe_once()

        assert mqtt_gate.subscribe.await_count == 2

    await scenario()


async def test_add_replaces_active_broker_subscriptions() -> None:
    async def scenario() -> None:
        original = Subscription("SmartHome/old/#")
        added = Subscription("SmartHome/new/#", qos=2)
        manager, mqtt_gate, _ = build_manager([original])
        await manager.activate()

        await manager.add(added)

        mqtt_gate.unsubscribe.assert_awaited_once()
        assert manager.subscriptions == (original, added)
        assert mqtt_gate.subscribe.await_count == 2

    await scenario()


async def test_remove_replaces_active_broker_subscriptions() -> None:
    async def scenario() -> None:
        removed = Subscription("SmartHome/old/#")
        remaining = Subscription("SmartHome/+/status", qos=2)
        manager, mqtt_gate, _ = build_manager([removed, remaining])
        await manager.activate()

        await manager.remove(removed)

        mqtt_gate.unsubscribe.assert_awaited_once()
        assert manager.subscriptions == (remaining,)
        assert mqtt_gate.subscribe.await_count == 2

    await scenario()


async def test_update_replaces_active_broker_subscriptions() -> None:
    async def scenario() -> None:
        original = Subscription("SmartHome/old/#")
        replacement = Subscription("SmartHome/new/#", qos=2)
        manager, mqtt_gate, _ = build_manager([original])
        await manager.activate()

        await manager.update(original.topic_filter, replacement)

        mqtt_gate.unsubscribe.assert_awaited_once()
        assert manager.subscriptions == (replacement,)
        assert mqtt_gate.subscribe.await_count == 2

    await scenario()


async def test_subscription_changes_reject_missing_and_duplicate_filters() -> None:
    async def scenario() -> None:
        existing = Subscription("SmartHome/existing/#")
        other = Subscription("SmartHome/other/#")
        manager, _, _ = build_manager([existing, other])

        for operation in (
            manager.add(existing),
            manager.remove(Subscription("SmartHome/missing/#")),
            manager.update("SmartHome/missing/#", existing),
            manager.update(existing.topic_filter, other),
        ):
            try:
                await operation
            except ValueError:
                pass
            else:
                raise AssertionError("Expected subscription validation to fail")

    await scenario()
