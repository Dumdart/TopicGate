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
    broker_id: UUID | None
    entries: tuple[ObservationDeletionEntry, ...]
    scope: str = "broker"

    @property
    def broker_ids(self) -> tuple[UUID, ...]:
        return tuple(sorted({entry.broker_id for entry in self.entries}, key=str))

    @property
    def total_entries(self) -> int:
        return len(self.entries)

    @property
    def stored_payload_bytes(self) -> int:
        return sum(entry.stored_payload_bytes for entry in self.entries)

    @property
    def oldest_received_at(self) -> datetime | None:
        return min((entry.received_at for entry in self.entries), default=None)

    @property
    def newest_received_at(self) -> datetime | None:
        return max((entry.received_at for entry in self.entries), default=None)
