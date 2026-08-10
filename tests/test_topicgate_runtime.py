import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.broker_profile import BrokerProfile
from topicgate.core.models.observer_model import ObserverModel, TopicState
from topicgate.core.models.observer_workspace import ObserverWorkspace
from topicgate.core.models.subscription import Subscription


def profile(name: str, host: str = "broker") -> BrokerProfile:
    profile_id = uuid4()
    workspace = ObserverWorkspace(
        id=uuid4(),
        profile_id=profile_id,
        model=ObserverModel(root_stats=[]),
    )
    return BrokerProfile(
        profile_id,
        name,
        MqttConfig(host, 1883, "", ""),
        workspace.id,
        workspace,
    )


def runtime_with(
    profiles: tuple[BrokerProfile, ...],
) -> tuple[TopicGateRuntime, MagicMock, MagicMock]:
    brokers = MagicMock()
    active_id = profiles[0].id
    stored = {item.id: item for item in profiles}
    brokers.get_all_profiles.side_effect = lambda: tuple(stored.values())
    brokers.get_profile.side_effect = lambda broker_id=None: stored[
        active_id if broker_id is None else broker_id
    ]
    brokers.create_profile.side_effect = lambda name, config: profile(name, config.host)
    brokers.delete_profile.side_effect = lambda broker_id: stored.pop(broker_id)

    def activate(broker_id, mqtt=None) -> None:
        nonlocal active_id
        if mqtt is not None:
            stored[broker_id].config = mqtt
        active_id = broker_id

    brokers.activate_profile.side_effect = activate
    mqtt = MagicMock()
    mqtt.start = AsyncMock()
    mqtt.stop = AsyncMock()
    mqtt.connect = AsyncMock()
    mqtt.disconnect = AsyncMock()
    mqtt.reconnect = AsyncMock()
    mqtt.update_broker = AsyncMock()
    mqtt.add_subscription = AsyncMock()
    mqtt.update_subscription = AsyncMock()
    mqtt.remove_subscription = AsyncMock()
    mqtt.publish = AsyncMock()
    mqtt.get.return_value = ObserverModel(root_stats=[])
    mqtt.subscriptions = ()
    mqtt.connection_status = "disconnected"
    mqtt.dropped_message_count = 0
    mqtt.topic_update_interval = 0.1
    return TopicGateRuntime(brokers, mqtt), brokers, mqtt


def test_runtime_owns_the_mqtt_lifecycle() -> None:
    async def scenario() -> None:
        runtime, brokers, mqtt = runtime_with((profile("Default"),))

        await runtime.start()
        await runtime.stop()

        mqtt.start.assert_awaited_once_with()
        brokers.update_observer_model.assert_called_once_with(mqtt.get.return_value)
        mqtt.stop.assert_awaited_once_with()

    asyncio.run(scenario())


def test_runtime_activates_and_persists_a_broker_only_after_connecting() -> None:
    async def scenario() -> None:
        default = profile("Default")
        selected = profile("Local", "local")
        runtime, brokers, mqtt = runtime_with((default, selected))
        replacement = MqttConfig("secure", 8883, "user", "secret", True)

        active = await runtime.activate_broker(
            selected.id,
            replacement,
            "Local TLS",
        )

        mqtt.update_broker.assert_awaited_once_with(
            replacement,
            selected.workspace.model,
            selected.workspace.subscriptions,
        )
        brokers.update_profile.assert_called_once_with(selected)
        brokers.activate_profile.assert_called_once_with(selected.id, replacement)
        assert active.id == selected.id
        assert active.name == "Local TLS"

    asyncio.run(scenario())


def test_runtime_does_not_persist_a_failed_broker_activation() -> None:
    async def scenario() -> None:
        selected = profile("Default")
        runtime, brokers, mqtt = runtime_with((selected,))
        mqtt.update_broker.side_effect = ConnectionError("unavailable")

        try:
            await runtime.activate_broker(
                selected.id,
                MqttConfig("new", 1883, "", ""),
            )
        except ConnectionError:
            pass
        else:
            raise AssertionError("Expected broker activation to fail")

        brokers.update_profile.assert_not_called()
        brokers.activate_profile.assert_not_called()

    asyncio.run(scenario())


def test_runtime_persists_subscription_changes_to_the_active_workspace() -> None:
    async def scenario() -> None:
        active = profile("Default")
        runtime, brokers, mqtt = runtime_with((active,))
        subscription = Subscription("home/#")
        mqtt.subscriptions = (subscription,)

        await runtime.add_subscription(active.id, subscription)
        updated = Subscription("house/#", qos=2)
        mqtt.subscriptions = (updated,)
        await runtime.update_subscription(
            active.id,
            subscription.topic_filter,
            updated,
        )
        mqtt.subscriptions = ()
        await runtime.remove_subscription(active.id, updated)

        mqtt.add_subscription.assert_awaited_once_with(subscription)
        mqtt.update_subscription.assert_awaited_once_with(
            subscription.topic_filter,
            updated,
        )
        mqtt.remove_subscription.assert_awaited_once_with(updated)
        assert active.workspace.subscriptions == ()
        assert brokers.update_observer_workspace.call_count == 3

    asyncio.run(scenario())


def test_runtime_exposes_topic_queries_connection_commands_and_publish() -> None:
    async def scenario() -> None:
        active = profile("Default")
        state = TopicState(
            name="status",
            topic="home/status",
            payload=b"on",
            qos=1,
            retain=False,
            recieved_at=datetime.now(timezone.utc),
        )
        runtime, _, mqtt = runtime_with((active,))
        mqtt.get_state.return_value = state

        assert runtime.get_topic_state(active.id, "home/status") is state
        await runtime.connect()
        await runtime.reconnect()
        await runtime.disconnect()
        await runtime.publish(active.id, "home/set", b"off")

        mqtt.connect.assert_awaited_once_with()
        mqtt.reconnect.assert_awaited_once_with()
        mqtt.disconnect.assert_awaited_once_with()
        mqtt.publish.assert_awaited_once_with("home/set", b"off")

    asyncio.run(scenario())


def test_runtime_exposes_mqtt_event_streams() -> None:
    active = profile("Default")
    runtime, _, mqtt = runtime_with((active,))
    message_stream = object()
    connection_stream = object()
    mqtt.messages.return_value = message_stream
    mqtt.connection_statuses.return_value = connection_stream

    assert runtime.messages() is message_stream
    assert runtime.connection_statuses() is connection_stream


def test_runtime_creates_updates_and_deletes_broker_profiles() -> None:
    async def scenario() -> None:
        default = profile("Default")
        removable = profile("Remote")
        runtime, brokers, _ = runtime_with((default, removable))
        created = runtime.create_broker(
            "New",
            MqttConfig("new", 1883, "", ""),
        )
        updated = runtime.update_broker(
            removable.id,
            MqttConfig("remote", 1883, "", ""),
            "Renamed",
        )
        deleted = await runtime.delete_broker(removable.id)

        brokers.create_profile.assert_called_once()
        brokers.update_profile.assert_called_once_with(removable)
        assert created.name == "New"
        assert updated.name == "Renamed"
        assert deleted is removable

    asyncio.run(scenario())
