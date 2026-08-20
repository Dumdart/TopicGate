from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from topicgate.core.models.observation_deletion_preview import (
    ObservationDeletionEntry,
    ObservationDeletionPreview,
)
from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)


class RetentionRemovalReason(StrEnum):
    EXPIRED = "expired"
    PER_BROKER_ENTRY_LIMIT = "per_broker_entry_limit"
    PER_BROKER_BYTE_LIMIT = "per_broker_byte_limit"
    GLOBAL_ENTRY_LIMIT = "global_entry_limit"
    GLOBAL_BYTE_LIMIT = "global_byte_limit"
    UNSUBSCRIBED = "unsubscribed"


@dataclass(frozen=True)
class BrokerCacheUsage:
    broker_id: UUID
    entry_count: int
    stored_payload_bytes: int
    oldest_received_at: datetime | None
    newest_received_at: datetime | None


@dataclass(frozen=True)
class CacheUsageSummary:
    brokers: tuple[BrokerCacheUsage, ...]

    @property
    def entry_count(self) -> int:
        return sum(item.entry_count for item in self.brokers)

    @property
    def stored_payload_bytes(self) -> int:
        return sum(item.stored_payload_bytes for item in self.brokers)

    @property
    def oldest_received_at(self) -> datetime | None:
        return min(
            (
                item.oldest_received_at
                for item in self.brokers
                if item.oldest_received_at is not None
            ),
            default=None,
        )

    @property
    def newest_received_at(self) -> datetime | None:
        return max(
            (
                item.newest_received_at
                for item in self.brokers
                if item.newest_received_at is not None
            ),
            default=None,
        )


@dataclass(frozen=True)
class PersistedTopicSummary:
    broker_id: UUID
    topic: str
    observation_id: UUID
    stored_payload_bytes: int
    received_at: datetime
    is_subscribed: bool


@dataclass(frozen=True)
class RetentionImpactGroup:
    broker_id: UUID
    reason: RetentionRemovalReason
    entries: tuple[ObservationDeletionEntry, ...]

    @property
    def stored_payload_bytes(self) -> int:
        return sum(item.stored_payload_bytes for item in self.entries)


@dataclass(frozen=True)
class RetentionPolicyPreview:
    previous_policy: ObservationRetentionPolicy
    proposed_policy: ObservationRetentionPolicy
    deletion: ObservationDeletionPreview
    groups: tuple[RetentionImpactGroup, ...]

    @property
    def has_deletions(self) -> bool:
        return bool(self.deletion.entries)


@dataclass(frozen=True)
class ObservationDeletionResult:
    previewed_entries: tuple[ObservationDeletionEntry, ...]
    deleted_entries: tuple[ObservationDeletionEntry, ...]
    skipped_entries: tuple[ObservationDeletionEntry, ...]

    @property
    def previewed_count(self) -> int:
        return len(self.previewed_entries)

    @property
    def deleted_count(self) -> int:
        return len(self.deleted_entries)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped_entries)

    @property
    def deleted_bytes(self) -> int:
        return sum(item.stored_payload_bytes for item in self.deleted_entries)

    @property
    def skipped_bytes(self) -> int:
        return sum(item.stored_payload_bytes for item in self.skipped_entries)

    @property
    def is_partial(self) -> bool:
        return bool(self.skipped_entries)


@dataclass(frozen=True)
class RetentionPolicyApplicationResult:
    policy: ObservationRetentionPolicy
    enforcement: ObservationDeletionResult
