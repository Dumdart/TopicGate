from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class BrokerProfileIdentity:
    """Persisted identity and display metadata for a broker profile."""

    id: UUID
    name: str
    position: int
    is_active: bool
    workspace_id: UUID

