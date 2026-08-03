import pytest

from smart_home_observer.core.models.chicken_door import ChickenDoor
from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.infrastructure.processors.chicken_door_mqtt_message_processor import (
    ChickenDoorMqttMessageProcessor,
)


@pytest.mark.parametrize(
    ("topic", "payload", "attribute", "expected"),
    [
        ("home/command", b"open_door", "command", "open_door"),
        ("home/status", b"open", "status", "open"),
        ("home/status_code", b"1", "status_code", 1),
        ("home/fault", b"none", "fault", "none"),
        ("home/connected", b"true", "connected", True),
        ("home/connected", b"false", "connected", False),
        ("home/battery", b"100", "battery", 100),
        ("home/light_level", b"100", "light_level", 100),
    ],
)
def test_process_updates_the_matching_chicken_door_field(
    topic: str, payload: bytes, attribute: str, expected: object
) -> None:
    state = ChickenDoor("", "", -1, "", False, -1, -1)
    message = MqttMessage(topic, payload, qos=1, retain=False)

    ChickenDoorMqttMessageProcessor().process(state, message)

    assert getattr(state, attribute) == expected
