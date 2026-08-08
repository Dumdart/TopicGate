from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.observer_model import ObserverModel
from smart_home_observer.processors.observer_model_mqtt_message_processor import (
    ObserverModelMqttMessageProcessor,
)
from smart_home_observer.services.observer_model_service import ObserverModelService


def build_model(*topics: str) -> ObserverModel:
    return ObserverModelService.add_topics(
        ObserverModel(root_stats=[]),
        topics,
    )


def test_process_stores_message_state_on_the_matching_topic_node() -> None:
    model = build_model("SmartHome/Huehnerstall/door/status")
    message = MqttMessage(
        "SmartHome/Huehnerstall/door/status", b"open", qos=1, retain=True
    )

    ObserverModelMqttMessageProcessor().process(model, message)

    node = ObserverModelService.find_node(model, message.topic)

    assert node is not None
    assert node.state is not None
    assert node.state.name == "status"
    assert node.state.topic == message.topic
    assert node.state.payload == b"open"
    assert node.state.qos == 1
    assert node.state.retain is True
    assert node.state.recieved_at.tzinfo is not None


def test_process_stores_messages_for_discovered_topics() -> None:
    model = build_model()
    message = MqttMessage("SmartHome/unknown", b"value", qos=0, retain=False)

    ObserverModelMqttMessageProcessor().process(model, message)

    assert model.topic_states[message.topic].payload == b"value"
    assert ObserverModelService.find_node(model, message.topic) is not None


def test_process_counts_messages_per_topic() -> None:
    model = build_model()
    processor = ObserverModelMqttMessageProcessor()

    processor.process(model, MqttMessage("SmartHome/device/value", b"1", 0, False))
    processor.process(model, MqttMessage("SmartHome/device/value", b"2", 0, False))

    assert model.topic_states["SmartHome/device/value"].message_count == 2
