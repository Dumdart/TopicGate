from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ObservationDeletionEntry:
    broker_id: UUID
    topic: str
    observation_id: UUID
    received_at: datetime
    stored_payload_bytes: int


@dataclass(frozen=True)
class ObservationDeletionPreview:
    broker_id: UUID
    entries: tuple[ObservationDeletionEntry, ...]

    @property
    def total_entries(self) -> int:
        return len(self.entries)

    @property
    def stored_payload_bytes(self) -> int:
        return sum(entry.stored_payload_bytes for entry in self.entries)
