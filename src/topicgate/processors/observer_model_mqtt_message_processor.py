from datetime import datetime, timezone

from topicgate.core.interfaces.mqtt_message_processor import MqttMessageProcessor
from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.core.models.observer_model import ObserverModel, TopicState
from topicgate.core.mqtt_topics import validate_topic_name
from topicgate.core.observer_limits import (
    MAX_OBSERVED_TOPICS,
    MAX_RETAINED_PAYLOAD_BYTES,
    ObserverModelCapacityError,
)
from topicgate.services.observer_model_service import ObserverModelService


class ObserverModelMqttMessageProcessor(MqttMessageProcessor[ObserverModel]):
    def process(self, state: ObserverModel, message: MqttMessage) -> bool:
        validate_topic_name(message.topic)
        previous_state = state.topic_states.get(message.topic)
        if len(message.payload) > MAX_RETAINED_PAYLOAD_BYTES:
            return False

        if previous_state is None:
            while len(state.topic_states) >= MAX_OBSERVED_TOPICS:
                if not self._evict_oldest(state, message.topic):
                    return False

        retained_bytes = sum(
            len(topic_state.payload)
            for topic_state in state.topic_states.values()
        ) - (0 if previous_state is None else len(previous_state.payload))
        while retained_bytes + len(message.payload) > MAX_RETAINED_PAYLOAD_BYTES:
            removed = self._evict_oldest(state, message.topic)
            if removed is None:
                return False
            retained_bytes -= len(removed.payload)

        while True:
            try:
                node = ObserverModelService.find_or_create_node(
                    state, message.topic
                )
                break
            except ObserverModelCapacityError:
                if not self._evict_oldest(state, message.topic):
                    return False

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
        return True

    @staticmethod
    def _evict_oldest(
        state: ObserverModel,
        excluded_topic: str,
    ) -> TopicState | None:
        candidates = (
            topic_state
            for topic, topic_state in state.topic_states.items()
            if topic != excluded_topic
        )
        oldest = min(candidates, key=lambda item: item.recieved_at, default=None)
        if oldest is None:
            return None
        return ObserverModelService.remove_topic(state, oldest.topic)
