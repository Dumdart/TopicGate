from datetime import datetime, timezone

from topicgate.core.interfaces.mqtt_message_processor import MqttMessageProcessor
from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.core.models.observer_model import ObserverModel, TopicState
from topicgate.core.mqtt_topics import validate_topic_name
from topicgate.services.observer_model_service import ObserverModelService


class ObserverModelMqttMessageProcessor(MqttMessageProcessor[ObserverModel]):
    def process(self, state: ObserverModel, message: MqttMessage) -> None:
        validate_topic_name(message.topic)
        node = ObserverModelService.find_or_create_node(state, message.topic)
        previous_state = state.topic_states.get(message.topic)
        topic_state = TopicState(
            name=node.segment,
            topic=message.topic,
            payload=message.payload,
            qos=message.qos,
            retain=message.retain,
            recieved_at=datetime.now(timezone.utc),
            payload_size=message.payload_size,
            message_count=(
                1 if previous_state is None else previous_state.message_count + 1
            ),
        )
        node.state = topic_state
        state.topic_states[message.topic] = topic_state
