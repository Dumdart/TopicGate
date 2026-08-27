from typing import Protocol

from topicgate.core.models.observation_cache_administration import (
    ObservationDeletionResult,
)
from topicgate.core.models.observation_deletion_preview import (
    ObservationDeletionPreview,
)


class StoredObservationAdministrator(Protocol):
    """Mutate persisted observations and coordinate queued writes."""

    def enforce_retention(self) -> None: ...

    def delete_previewed_detailed(
        self,
        preview: ObservationDeletionPreview,
    ) -> ObservationDeletionResult: ...

    def flush(self) -> None: ...
