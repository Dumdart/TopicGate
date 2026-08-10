from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.core.models.observer_model import ObserverModel
from topicgate.core.mqtt_topics import (
    MAX_MQTT_TOPIC_BYTES,
    MAX_MQTT_TOPIC_LEVELS,
)
from topicgate.core.observer_limits import (
    MAX_OBSERVED_TOPICS,
    MAX_OBSERVER_NODES,
    MAX_RETAINED_PAYLOAD_BYTES,
)
from topicgate.processors.observer_model_mqtt_message_processor import (
    ObserverModelMqttMessageProcessor,
)
from topicgate.services.observer_model_service import ObserverModelService


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


def test_process_preserves_original_size_of_a_truncated_payload() -> None:
    model = build_model()
    message = MqttMessage(
        "untrusted/topic", b"truncated", 0, False, payload_size=100_000
    )

    ObserverModelMqttMessageProcessor().process(model, message)

    assert model.topic_states[message.topic].payload == b"truncated"
    assert model.topic_states[message.topic].payload_size == 100_000


def test_process_rejects_unsafe_received_topics_before_mutation() -> None:
    unsafe_topics = (
        "/".join("a" for _ in range(MAX_MQTT_TOPIC_LEVELS + 1)),
        "a" * (MAX_MQTT_TOPIC_BYTES + 1),
        "home/+/status",
    )

    for topic in unsafe_topics:
        model = build_model()
        try:
            ObserverModelMqttMessageProcessor().process(
                model, MqttMessage(topic, b"value", 0, False)
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Expected an unsafe topic name to fail")

        assert model.root_stats == []
        assert model.topic_states == {}


def test_process_accepts_received_topic_at_depth_limit() -> None:
    model = build_model()
    topic = "/".join("a" for _ in range(MAX_MQTT_TOPIC_LEVELS))

    ObserverModelMqttMessageProcessor().process(
        model, MqttMessage(topic, b"value", 0, False)
    )

    assert len(ObserverModelService.get_all_nodes(model)) == MAX_MQTT_TOPIC_LEVELS
    assert model.topic_states[topic].payload == b"value"


def test_distinct_topic_flood_evicts_least_recently_used_state() -> None:
    model = build_model("devices/#")
    processor = ObserverModelMqttMessageProcessor()

    for index in range(MAX_OBSERVED_TOPICS):
        assert processor.process(
            model, MqttMessage(f"devices/{index}", b"value", 0, False)
        )
    assert processor.process(
        model, MqttMessage("devices/0", b"recent", 0, False)
    )
    assert processor.process(
        model, MqttMessage("devices/overflow", b"new", 0, False)
    )

    assert len(model.topic_states) == MAX_OBSERVED_TOPICS
    assert "devices/0" in model.topic_states
    assert "devices/1" not in model.topic_states
    assert "devices/overflow" in model.topic_states
    assert ObserverModelService.find_node(model, "devices/#") is not None
    assert len(ObserverModelService.get_all_nodes(model)) <= MAX_OBSERVER_NODES


def test_retained_payload_bytes_are_bounded() -> None:
    model = build_model("devices/#")
    processor = ObserverModelMqttMessageProcessor()
    payload = b"x" * (64 * 1024)
    message_total = MAX_RETAINED_PAYLOAD_BYTES // len(payload) + 1

    for index in range(message_total):
        assert processor.process(
            model, MqttMessage(f"devices/{index}", payload, 0, False)
        )

    assert sum(
        len(state.payload) for state in model.topic_states.values()
    ) <= MAX_RETAINED_PAYLOAD_BYTES
    assert "devices/0" not in model.topic_states
    assert f"devices/{message_total - 1}" in model.topic_states
