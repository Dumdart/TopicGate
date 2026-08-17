from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ObservationSource(StrEnum):
    """How an observation entered the current application process."""

    STORED = "stored"
    LIVE = "live"


@dataclass
class MqttObservation:
    """The latest MQTT value observed for one topic."""

    name: str
    topic: str
    payload: bytes
    qos: int
    retain: bool
    recieved_at: datetime
    message_count: int = 1
    payload_size: int | None = None
    source: ObservationSource = ObservationSource.LIVE
    observation_id: UUID | None = None
    connection_id: UUID | None = None

    def __post_init__(self) -> None:
        self.payload_size = max(self.payload_size or 0, len(self.payload))

    @property
    def received_at(self) -> datetime:
        """Return the receive time with its correctly spelled public name."""
        return self.recieved_at
