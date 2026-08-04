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
        )
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


def test_repository_subscribes_to_its_configured_absolute_topics() -> None:
    repository = ObserverRepository(
        MqttConfig(host="broker", port=1883, username="", password="")
    )

    assert repository._mqtt_gate.topics == [
        "SmartHome/Huehnerstall/door/command",
        "SmartHome/Huehnerstall/door/status",
        "SmartHome/Huehnerstall/door/status_code",
        "SmartHome/Huehnerstall/door/fault",
        "SmartHome/Huehnerstall/door/connected",
        "SmartHome/Huehnerstall/door/battery",
        "SmartHome/Huehnerstall/door/light_level",
    ]
