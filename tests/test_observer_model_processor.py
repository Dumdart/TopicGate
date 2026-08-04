from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.processors.observer_model_mqtt_message_processor import (
    ObserverModelMqttMessageProcessor,
)
from smart_home_observer.services.observer_model_service import ObserverModelService
from smart_home_observer.services.topic_service import TopicService


def test_process_stores_message_state_on_the_matching_topic_node() -> None:
    model = TopicService.get_topics()
    message = MqttMessage(
        "home/chicken-door/status", b"open", qos=1, retain=True
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


def test_process_ignores_messages_for_unconfigured_topics() -> None:
    model = TopicService.get_topics()

    ObserverModelMqttMessageProcessor().process(
        model, MqttMessage("home/unknown", b"value", qos=0, retain=False)
    )

    assert ObserverModelService.get_all_states(model) == []
