import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.observer_model import ObserverModel, TopicState
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.gui.main_view_model import MainViewModel, mqtt_filter_matches


class FakeObserverRepository:
    def __init__(self) -> None:
        self._states: dict[str, TopicState] = {}
        self._messages: asyncio.Queue[MqttMessage] = asyncio.Queue()
        self.subscriptions: tuple[Subscription, ...] = ()
        self.connection_operations: list[str] = []
        self.removed_subscriptions: list[Subscription] = []
        self.broker_configurations: list[MqttConfig] = []

    def get(self) -> ObserverModel:
        return ObserverModel(root_stats=[], topic_states=dict(self._states))

    def get_state(self, topic: str) -> TopicState | None:
        return self._states.get(topic)

    async def messages(self) -> AsyncIterator[MqttMessage]:
        while True:
            yield await self._messages.get()

    def publish(self, message: MqttMessage) -> None:
        self._states[message.topic] = TopicState(
            name=message.topic.rsplit("/", maxsplit=1)[-1],
            topic=message.topic,
            payload=message.payload,
            qos=message.qos,
            retain=message.retain,
            recieved_at=datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc),
        )
        self._messages.put_nowait(message)

    async def connect(self) -> None:
        self.connection_operations.append("connect")

    async def reconnect(self) -> None:
        self.connection_operations.append("reconnect")

    async def disconnect(self) -> None:
        self.connection_operations.append("disconnect")

    async def update_broker(self, new_config: MqttConfig) -> None:
        self.broker_configurations.append(new_config)

    async def remove_subscription(self, subscription: Subscription) -> None:
        self.removed_subscriptions.append(subscription)
        self.subscriptions = tuple(
            item for item in self.subscriptions if item != subscription
        )


class FakeConfigRepository:
    def __init__(self, mqtt: MqttConfig) -> None:
        self._mqtt = mqtt
        self.updated_mqtt: list[MqttConfig] = []

    def get_mqtt(self) -> MqttConfig:
        return self._mqtt

    def update_mqtt(self, mqtt: MqttConfig) -> None:
        self._mqtt = mqtt
        self.updated_mqtt.append(mqtt)


def test_view_model_displays_and_refreshes_the_selected_topic_state() -> None:
    async def scenario() -> None:
        topic = "SmartHome/Huehnerstall/door/status"
        repository = FakeObserverRepository()
        view_model = MainViewModel(repository, topic)

        assert view_model.value == "Waiting for a message"

        await view_model.start()
        repository.publish(MqttMessage(topic, b"open", qos=1, retain=True))
        await asyncio.sleep(0)

        assert view_model.topic == topic
        assert view_model.value == "open"
        assert view_model.quality_of_service == "1"
        assert view_model.retained == "True"
        assert view_model.received_at == "2026-08-04T12:00:00+00:00"

        await view_model.stop()

    asyncio.run(scenario())


def test_discovered_topic_updates_details_and_only_matching_filter_is_editable() -> None:
    repository = FakeObserverRepository()
    repository.subscriptions = (Subscription("SmartHome/+/status", qos=2),)
    repository.publish(MqttMessage("SmartHome/kitchen/status", b"open", 1, False))
    repository.publish(MqttMessage("Other/device/value", b"42", 0, False))
    view_model = MainViewModel(repository)

    view_model.select_topic("SmartHome/kitchen/status")

    assert view_model.decoded_payload == "open"
    assert view_model.selected_subscription == repository.subscriptions[0]

    view_model.select_topic("Other/device/value")

    assert view_model.decoded_payload == "42"
    assert view_model.selected_subscription is None


def test_topic_paths_include_configured_filters_and_discovered_topics() -> None:
    repository = FakeObserverRepository()
    repository.subscriptions = (Subscription("SmartHome/#"),)
    repository.publish(MqttMessage("SmartHome/kitchen/temperature", b"21", 0, False))

    assert MainViewModel(repository).topic_paths == [
        "SmartHome/#",
        "SmartHome/kitchen/temperature",
    ]


def test_topic_paths_exclude_discovered_topics_without_an_active_filter() -> None:
    repository = FakeObserverRepository()
    repository.subscriptions = (Subscription("SmartHome/#"),)
    repository.publish(MqttMessage("SmartHome/kitchen/status", b"open", 1, False))
    repository.publish(MqttMessage("Other/device/status", b"open", 1, False))

    assert MainViewModel(repository).topic_paths == [
        "SmartHome/#",
        "SmartHome/kitchen/status",
    ]


def test_mqtt_filter_matching_supports_wildcards_and_system_topic_rules() -> None:
    assert mqtt_filter_matches("home/+/temperature", "home/kitchen/temperature")
    assert mqtt_filter_matches("home/#", "home/kitchen/temperature")
    assert mqtt_filter_matches("home/#", "home")
    assert not mqtt_filter_matches("home/+/temperature", "home/temperature")
    assert not mqtt_filter_matches("#", "$SYS/broker/uptime")
    assert mqtt_filter_matches("$SYS/#", "$SYS/broker/uptime")


def test_connection_commands_are_forwarded_to_the_repository() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        view_model = MainViewModel(repository)

        await view_model.connect_to_broker()
        await view_model.reconnect_to_broker()
        await view_model.disconnect_from_broker()

        assert repository.connection_operations == [
            "connect",
            "reconnect",
            "disconnect",
        ]

    asyncio.run(scenario())


def test_mqtt_configuration_is_applied_then_stored() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        initial = MqttConfig("old", 1883, "", "")
        config_repository = FakeConfigRepository(initial)
        view_model = MainViewModel(
            repository,
            config_repository=config_repository,
        )
        replacement = MqttConfig("new", 8883, "observer", "password", True)
        logs: list[str] = []
        changes: list[bool] = []
        view_model.log_message.connect(logs.append)
        view_model.configuration_changed.connect(lambda: changes.append(True))

        await view_model.update_mqtt_config(replacement)

        assert view_model.mqtt_config == replacement
        assert repository.broker_configurations == [replacement]
        assert config_repository.updated_mqtt == [replacement]
        assert changes == [True]
        assert logs == [
            "Connecting to MQTT broker: new:8883",
            "Updated MQTT broker: new:8883",
        ]

    asyncio.run(scenario())


def test_failed_mqtt_configuration_is_not_stored() -> None:
    class FailingObserverRepository(FakeObserverRepository):
        async def update_broker(self, new_config: MqttConfig) -> None:
            raise ConnectionError("broker unavailable")

    async def scenario() -> None:
        initial = MqttConfig("old", 1883, "", "")
        config_repository = FakeConfigRepository(initial)
        view_model = MainViewModel(
            FailingObserverRepository(),
            config_repository=config_repository,
        )
        logs: list[str] = []
        view_model.log_message.connect(logs.append)

        try:
            await view_model.update_mqtt_config(MqttConfig("new", 8883, "", ""))
        except ConnectionError:
            pass
        else:
            raise AssertionError("Expected the broker update to fail")

        assert view_model.mqtt_config == initial
        assert config_repository.updated_mqtt == []
        assert logs == [
            "Connecting to MQTT broker: new:8883",
            "Broker update failed: broker unavailable",
        ]

    asyncio.run(scenario())


def test_removing_subscription_updates_topics_and_clears_stale_selection() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        subscription = Subscription("SmartHome/#")
        repository.subscriptions = (subscription,)
        view_model = MainViewModel(repository, subscription.topic_filter)
        changed: list[str] = []
        logs: list[str] = []
        view_model.state_changed.connect(lambda: changed.append("state"))
        view_model.topics_changed.connect(lambda: changed.append("topics"))
        view_model.subscriptions_changed.connect(
            lambda: changed.append("subscriptions")
        )
        view_model.log_message.connect(logs.append)

        await view_model.remove_subscription(subscription)

        assert repository.removed_subscriptions == [subscription]
        assert repository.subscriptions == ()
        assert view_model.topic == ""
        assert changed == ["state", "topics", "subscriptions"]
        assert logs == ["Removed subscription: SmartHome/#"]

    asyncio.run(scenario())


def test_removing_subscription_hides_its_cached_topic_and_clears_selection() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        subscription = Subscription("SmartHome/kitchen/status")
        repository.subscriptions = (subscription,)
        repository.publish(
            MqttMessage(subscription.topic_filter, b"open", 1, False)
        )
        view_model = MainViewModel(repository, subscription.topic_filter)

        await view_model.remove_subscription(subscription)

        assert view_model.topic == ""
        assert view_model.topic_paths == []

    asyncio.run(scenario())


def test_removing_subscription_keeps_topics_covered_by_another_filter() -> None:
    async def scenario() -> None:
        repository = FakeObserverRepository()
        removed = Subscription("SmartHome/kitchen/status")
        remaining = Subscription("SmartHome/#")
        repository.subscriptions = (removed, remaining)
        repository.publish(MqttMessage(removed.topic_filter, b"open", 1, False))
        view_model = MainViewModel(repository, removed.topic_filter)

        await view_model.remove_subscription(removed)

        assert view_model.topic == removed.topic_filter
        assert view_model.topic_paths == [
            remaining.topic_filter,
            removed.topic_filter,
        ]

    asyncio.run(scenario())
