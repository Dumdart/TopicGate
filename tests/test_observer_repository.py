from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.infrastructure.repository.observer_repository import (
    ObserverRepository,
)


def test_repository_returns_state_and_value_by_topic_path() -> None:
    repository = ObserverRepository(
        MqttConfig(
            host="broker",
            port=1883,
            username="",
            password="",
        ),
        ["SmartHome/#"],
    )
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


def test_repository_updates_topic_state_before_queuing_message() -> None:
    repository = ObserverRepository(
        MqttConfig(host="broker", port=1883, username="", password=""),
        ["SmartHome/#"],
    )
    message = MqttMessage("SmartHome/discovered/value", b"42", qos=0, retain=False)

    repository.handle_message(None, None, message)

    assert repository.get_value(message.topic) == b"42"
    assert asyncio.run(repository.message_queue.get()) == message


def test_repository_subscribes_to_its_configured_absolute_topic_filters() -> None:
    topic_filters = ["/SmartHome/Huehnerstall/door/#", "SmartHome/+/status"]
    repository = ObserverRepository(
        MqttConfig(host="broker", port=1883, username="", password=""),
        topic_filters,
    )

    assert repository._mqtt_gate.topics == topic_filters
import asyncio
