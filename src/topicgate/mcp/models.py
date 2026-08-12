from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class TopicStateResult:
    """JSON-safe representation of an observed MQTT topic state."""

    name: str
    topic: str
    payload_text: str | None
    payload_base64: str
    qos: int
    retain: bool
    received_at: datetime
    message_count: int
    payload_size: int


@dataclass(frozen=True)
class ConnectionStatusResult:
    """Connection health for the active MQTT broker profile."""

    broker_id: UUID
    status: str
    dropped_message_count: int
    topic_update_interval: float
