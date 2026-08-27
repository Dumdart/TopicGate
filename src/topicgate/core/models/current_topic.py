from dataclasses import dataclass

from topicgate.core.models.observation_status import ObservationStatus
from topicgate.core.models.topic_message import TopicMessage


@dataclass(frozen=True)
class CurrentTopic:
    """An atomic snapshot of a topic message and its observation status."""

    message: TopicMessage
    status: ObservationStatus
