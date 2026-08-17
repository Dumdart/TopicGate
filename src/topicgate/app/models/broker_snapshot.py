from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from topicgate.core.models.mqtt_observation import ObservationSource


class SnapshotPayloadEncoding(StrEnum):
    UTF8 = "utf-8"
    BASE64 = "base64"


class SnapshotLimitation(StrEnum):
    CURRENT_STATE_ONLY = "current_state_only"
    RETAINED_DELIVERY_UNCONFIRMED = "retained_delivery_unconfirmed"
    BROKER_DISCONNECTED = "broker_disconnected"
    OBSERVATION_NOT_STARTED = "observation_not_started"
    STORED_STATE_PREDATES_OBSERVATION = "stored_state_predates_observation"
    DROPPED_MESSAGES = "dropped_messages"
    STALE_STATES_OMITTED = "stale_states_omitted"
    RESULT_LIMIT_REACHED = "result_limit_reached"
    PAYLOAD_TRUNCATED = "payload_truncated"


@dataclass(frozen=True)
class SnapshotBrokerIdentity:
    id: UUID
    name: str


@dataclass(frozen=True)
class SnapshotPayload:
    encoding: SnapshotPayloadEncoding
    value: str
    original_size: int
    available_size: int
    rendered_size: int
    ingestion_truncated: bool
    rendering_truncated: bool
    truncated: bool


@dataclass(frozen=True)
class SnapshotTopicState:
    topic: str
    payload: SnapshotPayload
    qos: int
    retain: bool
    received_at: datetime
    age_seconds: float
    message_count: int
    source: ObservationSource


@dataclass(frozen=True)
class SnapshotFreshness:
    max_age_seconds: float | None
    stale_count: int


@dataclass(frozen=True)
class SnapshotResultLimit:
    limit: int
    total: int
    returned: int
    omitted: int
    omitted_as_stale: int
    omitted_by_limit: int
    truncated: bool


@dataclass(frozen=True)
class SnapshotSettling:
    requested_seconds: float
    maximum_seconds: float
    actual_seconds: float


@dataclass(frozen=True)
class SnapshotCompleteness:
    is_complete: bool
    limitations: tuple[SnapshotLimitation, ...]


@dataclass(frozen=True)
class BrokerSnapshot:
    broker: SnapshotBrokerIdentity
    connection_status: str
    captured_at: datetime
    connected_at: datetime | None
    observation_started_at: datetime | None
    observed_for_seconds: float | None
    topic_filter: str
    topics: tuple[SnapshotTopicState, ...]
    dropped_message_count: int
    freshness: SnapshotFreshness
    results: SnapshotResultLimit
    settling: SnapshotSettling
    completeness: SnapshotCompleteness
