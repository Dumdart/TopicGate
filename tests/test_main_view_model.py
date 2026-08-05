import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.observer_model import ObserverModel, TopicState
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.gui.main_view_model import MainViewModel, mqtt_filter_matches


class FakeObserverRepository:
    def __init__(self) -> None:
        self._states: dict[str, TopicState] = {}
        self._messages: asyncio.Queue[MqttMessage] = asyncio.Queue()
        self.subscriptions: tuple[Subscription, ...] = ()

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


def test_mqtt_filter_matching_supports_wildcards_and_system_topic_rules() -> None:
    assert mqtt_filter_matches("home/+/temperature", "home/kitchen/temperature")
    assert mqtt_filter_matches("home/#", "home/kitchen/temperature")
    assert mqtt_filter_matches("home/#", "home")
    assert not mqtt_filter_matches("home/+/temperature", "home/temperature")
    assert not mqtt_filter_matches("#", "$SYS/broker/uptime")
    assert mqtt_filter_matches("$SYS/#", "$SYS/broker/uptime")
