from dataclasses import dataclass

from topicgate.core.models.observation_status import ObservationStatus
from topicgate.core.models.mqtt_observation import (
    MqttObservation,
    ObservationSource,
)
from topicgate.core.models.topic_message import TopicMessage


@dataclass(frozen=True)
class CurrentTopic:
    """An atomic snapshot of a topic message and its observation status."""

    message: TopicMessage
    status: ObservationStatus

    def to_observation(self) -> MqttObservation:
        """Project the canonical entry into the legacy topic-state shape."""
        message = self.message
        return MqttObservation(
            name=message.topic.rsplit("/", 1)[-1],
            topic=message.topic,
            payload=message.payload,
            qos=message.qos,
            retain=message.retain,
            recieved_at=message.received_at,
            message_count=message.message_count,
            payload_size=message.payload_size,
            source=(
                ObservationSource.STORED
                if self.status is ObservationStatus.CACHED
                else ObservationSource.LIVE
            ),
            observation_id=message.observation_id,
        )
