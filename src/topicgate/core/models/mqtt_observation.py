from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.core.models.topic_message import TopicMessage

class ObservationSource(StrEnum):
    STORED = "stored"
    LIVE = "live"


@dataclass(frozen=True)
class MqttObservation:
    broker_id: UUID
    topic: str
    payload: bytes
    qos: int
    retain: bool
    received_at: datetime
    payload_size: int
    message_count: int
    observation_id: UUID
    source: ObservationSource
    connection_id: UUID | None
