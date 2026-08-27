from collections.abc import Collection
from typing import Protocol
from uuid import UUID

from topicgate.core.models.observation_cache_administration import (
    CacheUsageSummary,
)
from topicgate.core.models.observation_deletion_preview import (
    ObservationDeletionPreview,
)


class StoredObservationReader(Protocol):
    """Read persisted observation metadata without changing the cache."""

    def preview_deletion(
        self,
        broker_id: UUID,
        topics: Collection[str] | None = None,
    ) -> ObservationDeletionPreview: ...

    def preview_all_deletion(self) -> ObservationDeletionPreview: ...

    def cache_usage(self) -> CacheUsageSummary: ...
