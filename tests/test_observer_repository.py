import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.connection_status import ConnectionStatus
from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.infrastructure.repository.observer_repository import (
    ObserverRepository,
)


def build_repository() -> tuple[ObserverRepository, MagicMock]:
    manager = MagicMock()
    manager.activate = AsyncMock()
    manager.deactivate = AsyncMock()
    manager.add = AsyncMock()
    manager.remove = AsyncMock()
    manager.update = AsyncMock()
    manager.subscribe_once = AsyncMock()
    manager.disconnect = MagicMock()
    manager.subscriptions = ()

    with patch(
        "smart_home_observer.infrastructure.repository.observer_repository.SubscriptionManager",
        return_value=manager,
    ):
        repository = ObserverRepository(
            MqttConfig(host="broker", port=1883, username="", password=""),
            ["SmartHome/#"],
        )

    return repository, manager


def test_repository_returns_state_and_value_by_topic_path() -> None:
    repository, _ = build_repository()
    message = MqttMessage(
        "SmartHome/Huehnerstall/door/status", b"open", qos=1, retain=True
    )

    repository.handle_message(None, None, message)

    state = repository.get_state(message.topic)

    assert state is not None
    assert state.topic == message.topic
    assert repository.get_value(message.topic) == b"open"
    assert repository.get_state("SmartHome/Huehnerstall/door/missing") is None
    assert repository.get_value("SmartHome/missing") is None


def test_repository_updates_topic_state_before_publishing_message() -> None:
    async def scenario() -> None:
        repository, _ = build_repository()
        message = MqttMessage(
            "SmartHome/discovered/value", b"42", qos=0, retain=False
        )
        stream = repository.messages()

        repository.handle_message(None, None, message)

        assert repository.get_value(message.topic) == b"42"
        assert await anext(stream) == message
        await stream.aclose()

    asyncio.run(scenario())


def test_repository_delegates_subscription_operations() -> None:
    async def scenario() -> None:
        repository, manager = build_repository()
        original = Subscription("SmartHome/old/#")
        replacement = Subscription("SmartHome/new/#", qos=2)
        manager.subscriptions = (original,)

        await repository.add_subscription(replacement)
        await repository.remove_subscription(original)
        await repository.update_subscription(original.topic_filter, replacement)

        assert repository.subscriptions == (original,)
        manager.add.assert_awaited_once_with(replacement)
        manager.remove.assert_awaited_once_with(original)
        manager.update.assert_awaited_once_with(original.topic_filter, replacement)

    asyncio.run(scenario())


def test_start_connects_then_activates_subscription_manager() -> None:
    async def scenario() -> None:
        repository, manager = build_repository()
        repository._mqtt_gate.start = AsyncMock()
        status_stream = repository.connection_statuses()

        await repository.start()

        repository._mqtt_gate.start.assert_awaited_once()
        manager.activate.assert_awaited_once()
        assert repository.connection_status == ConnectionStatus.CONNECTED
        assert await anext(status_stream) == ConnectionStatus.CONNECTING
        assert await anext(status_stream) == ConnectionStatus.CONNECTED
        await status_stream.aclose()

    asyncio.run(scenario())


def test_stop_deactivates_manager_before_stopping_mqtt_gate() -> None:
    async def scenario() -> None:
        repository, manager = build_repository()
        repository._is_running = True
        events: list[str] = []

        async def deactivate() -> None:
            events.append("deactivate")

        async def stop() -> None:
            events.append("stop")

        manager.deactivate.side_effect = deactivate
        repository._mqtt_gate.stop = AsyncMock(side_effect=stop)

        await repository.stop()

        assert events == ["deactivate", "stop"]
        assert repository.connection_status == ConnectionStatus.DISCONNECTED

    asyncio.run(scenario())


def test_connected_and_disconnected_callbacks_delegate_to_manager() -> None:
    async def scenario() -> None:
        repository, manager = build_repository()
        repository._is_running = True

        await repository._handle_connected()
        repository._handle_disconnected()

        manager.subscribe_once.assert_awaited_once()
        manager.disconnect.assert_called_once()
        assert repository.connection_status == ConnectionStatus.RECONNECTING

    asyncio.run(scenario())


def test_startup_failure_stops_gate_and_leaves_repository_disconnected() -> None:
    async def scenario() -> None:
        repository, manager = build_repository()
        repository._mqtt_gate.start = AsyncMock(
            side_effect=RuntimeError("broker unavailable")
        )
        repository._mqtt_gate.stop = AsyncMock()

        try:
            await repository.start()
        except ConnectionError:
            pass
        else:
            raise AssertionError("Expected startup to fail")

        repository._mqtt_gate.stop.assert_awaited_once()
        manager.activate.assert_not_awaited()
        assert repository.connection_status == ConnectionStatus.DISCONNECTED

    asyncio.run(scenario())
