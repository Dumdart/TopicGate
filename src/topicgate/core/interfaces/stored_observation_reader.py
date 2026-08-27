from collections.abc import Collection
from typing import Protocol
from uuid import UUID

from topicgate.core.models.message_filter import MessageFilter
from topicgate.core.models.observation_cache_administration import (
    CacheUsageSummary,
)
from topicgate.core.models.observation_deletion_preview import (
    ObservationDeletionPreview,
)
from topicgate.core.models.topic_message import TopicMessage


class StoredObservationReader(Protocol):
    """Read persisted observation metadata without changing the cache."""

    def preview_deletion(
        self,
        broker_id: UUID,
        topics: Collection[str] | None = None,
    ) -> ObservationDeletionPreview: ...

    def preview_all_deletion(self) -> ObservationDeletionPreview: ...

    def cache_usage(self) -> CacheUsageSummary: ...

    def get_message(self, message_id: UUID) -> TopicMessage: ...

    def get_latest_message(self, topic: str | None = None) -> TopicMessage: ...

    def get_messages(self, broker_id: UUID) -> tuple[TopicMessage, ...]: ...

    def search_message(
        self, message_filter: MessageFilter
    ) -> tuple[TopicMessage, ...]: ...
