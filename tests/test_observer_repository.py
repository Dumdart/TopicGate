import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.connection_status import ConnectionStatus
from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.core.models.observer_model import ObserverModel
from topicgate.core.models.subscription import Subscription
from topicgate.core.payload_limits import MAX_PENDING_MESSAGE_NOTIFICATIONS
from topicgate.infrastructure.repository.observer_mqtt_repository import (
    ObserverMqttRepository,
)
from topicgate.services.observer_model_service import ObserverModelService


def build_repository(
    model: ObserverModel | None = None,
) -> tuple[ObserverMqttRepository, MagicMock]:
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
        "topicgate.infrastructure.repository.observer_mqtt_repository.SubscriptionManager",
        return_value=manager,
    ):
        repository = ObserverMqttRepository(
            MqttConfig(host="broker", port=1883, username="", password=""),
            ["SmartHome/#"],
            model,
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


def test_repository_updates_the_broker_profile_observer_model() -> None:
    profile_model = ObserverModel(root_stats=[])
    repository, _ = build_repository(profile_model)
    message = MqttMessage("SmartHome/door/status", b"open", qos=1, retain=False)

    repository.handle_message(None, None, message)

    assert profile_model.topic_states[message.topic].payload == b"open"


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


def test_message_notification_backlog_is_bounded() -> None:
    repository, _ = build_repository()

    for index in range(MAX_PENDING_MESSAGE_NOTIFICATIONS + 1):
        repository.handle_message(
            None,
            None,
            MqttMessage("untrusted/topic", str(index).encode(), 0, False),
        )

    assert repository.message_queue.qsize() == MAX_PENDING_MESSAGE_NOTIFICATIONS
    assert repository.dropped_message_count == 1
    assert repository.message_queue.get_nowait().payload == b"1"
    assert repository.get_value("untrusted/topic") == str(
        MAX_PENDING_MESSAGE_NOTIFICATIONS
    ).encode()


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


def test_removing_subscription_clears_uncovered_retained_state() -> None:
    async def scenario() -> None:
        repository, manager = build_repository()
        removed = Subscription("devices/#")
        remaining = Subscription("sensors/#")
        manager.subscriptions = (removed, remaining)
        repository.handle_message(
            None,
            None,
            MqttMessage("devices/untrusted", b"value", 0, False),
        )
        repository.handle_message(
            None,
            None,
            MqttMessage("sensors/temperature", b"21", 0, False),
        )

        async def remove(_subscription: Subscription) -> None:
            manager.subscriptions = (remaining,)

        manager.remove.side_effect = remove
        await repository.remove_subscription(removed)

        assert repository.get_state("devices/untrusted") is None
        assert repository.get_value("sensors/temperature") == b"21"
        assert ObserverModelService.find_node(
            repository.get(), remaining.topic_filter
        ) is not None

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


def test_update_broker_replaces_gate_and_manager_preserving_subscriptions() -> None:
    async def scenario() -> None:
        repository, previous_manager = build_repository()
        subscription = Subscription("SmartHome/door/#", qos=2)
        previous_manager.subscriptions = (subscription,)
        repository._is_running = True
        previous_gate = repository._mqtt_gate
        previous_gate.stop = AsyncMock()

        replacement_gate = MagicMock()
        replacement_gate.is_started = False
        replacement_gate.start = AsyncMock()
        replacement_gate.stop = AsyncMock()
        replacement_manager = MagicMock()
        replacement_manager.activate = AsyncMock()

        new_config = MqttConfig(
            host="new-broker",
            port=8883,
            username="observer",
            password="secret",
            use_tls=True,
        )
        with (
            patch(
                "topicgate.infrastructure.repository.observer_mqtt_repository.MqttGate",
                return_value=replacement_gate,
            ) as mqtt_gate,
            patch(
                "topicgate.infrastructure.repository.observer_mqtt_repository.SubscriptionManager",
                return_value=replacement_manager,
            ) as subscription_manager,
        ):
            await repository.update_broker(new_config)

        previous_manager.deactivate.assert_awaited_once()
        previous_gate.stop.assert_awaited_once()
        mqtt_gate.assert_called_once()
        assert mqtt_gate.call_args.args[0] == new_config
        assert mqtt_gate.call_args.args[2] == [subscription]
        subscription_manager.assert_called_once_with(
            replacement_gate,
            repository.handle_message,
        )
        replacement_gate.start.assert_awaited_once()
        replacement_manager.activate.assert_awaited_once()

    asyncio.run(scenario())


def test_update_broker_replaces_subscriptions_for_the_selected_profile() -> None:
    async def scenario() -> None:
        repository, previous_manager = build_repository()
        previous_manager.subscriptions = (Subscription("SmartHome/default/#"),)
        profile_subscriptions = (Subscription("bridge/#", qos=2),)
        replacement_gate = MagicMock()
        replacement_gate.is_started = False
        replacement_gate.start = AsyncMock()
        replacement_gate.stop = AsyncMock()
        replacement_manager = MagicMock()
        replacement_manager.activate = AsyncMock()

        with (
            patch(
                "topicgate.infrastructure.repository.observer_mqtt_repository.MqttGate",
                return_value=replacement_gate,
            ) as mqtt_gate,
            patch(
                "topicgate.infrastructure.repository.observer_mqtt_repository.SubscriptionManager",
                return_value=replacement_manager,
            ),
        ):
            await repository.update_broker(
                MqttConfig("local", 1883, "", ""),
                subscriptions=profile_subscriptions,
            )

        assert mqtt_gate.call_args.args[2] == list(profile_subscriptions)

    asyncio.run(scenario())


def test_update_broker_connects_when_previously_disconnected() -> None:
    async def scenario() -> None:
        repository, _ = build_repository()
        replacement_gate = MagicMock()
        replacement_gate.is_started = False
        replacement_gate.start = AsyncMock()
        replacement_gate.stop = AsyncMock()
        replacement_manager = MagicMock()
        replacement_manager.activate = AsyncMock()

        with (
            patch(
                "topicgate.infrastructure.repository.observer_mqtt_repository.MqttGate",
                return_value=replacement_gate,
            ),
            patch(
                "topicgate.infrastructure.repository.observer_mqtt_repository.SubscriptionManager",
                return_value=replacement_manager,
            ),
        ):
            await repository.update_broker(
                MqttConfig("new-broker", 1883, "", "")
            )

        replacement_gate.start.assert_awaited_once()
        replacement_manager.activate.assert_awaited_once()
        assert repository.connection_status == ConnectionStatus.CONNECTED

    asyncio.run(scenario())


def test_failed_broker_update_restores_the_previous_connection() -> None:
    async def scenario() -> None:
        repository, previous_manager = build_repository()
        repository._is_running = True
        previous_gate = repository._mqtt_gate
        previous_gate.start = AsyncMock()
        previous_gate.stop = AsyncMock()
        replacement_gate = MagicMock()
        replacement_gate.is_started = False
        replacement_gate.start = AsyncMock(side_effect=RuntimeError("unavailable"))
        replacement_gate.stop = AsyncMock()
        replacement_manager = MagicMock()
        replacement_manager.activate = AsyncMock()

        with (
            patch(
                "topicgate.infrastructure.repository.observer_mqtt_repository.MqttGate",
                return_value=replacement_gate,
            ),
            patch(
                "topicgate.infrastructure.repository.observer_mqtt_repository.SubscriptionManager",
                return_value=replacement_manager,
            ),
        ):
            try:
                await repository.update_broker(MqttConfig("new-broker", 1883, "", ""))
            except ConnectionError:
                pass
            else:
                raise AssertionError("Expected the broker update to fail")

        assert repository._mqtt_gate is previous_gate
        assert repository._subscription_manager is previous_manager
        previous_gate.start.assert_awaited_once()
        assert repository.connection_status == ConnectionStatus.CONNECTED

    asyncio.run(scenario())
