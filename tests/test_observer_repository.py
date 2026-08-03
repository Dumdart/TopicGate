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
            base_topic="home",
        )
    )
    message = MqttMessage(
        "home/weather-station/temperature", b"21.5", qos=1, retain=True
    )

    repository.handle_message(None, None, message)

    state = repository.get_state(message.topic)

    assert state is not None
    assert state.topic == message.topic
    assert repository.get_value(message.topic) == b"21.5"
    assert repository.get_state("home/weather-station/missing") is None
    assert repository.get_value("home/missing") is None
