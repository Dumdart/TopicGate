from collections.abc import Collection
from typing import Protocol
from uuid import UUID

from topicgate.core.models.topic_message import TopicMessage


class TopicMessageRecorder(Protocol):
    def record_message(self, entry: TopicMessage) -> None:
        """Record the canonical, already-processed topic update.

        Implementations must update current state atomically before enqueueing
        the entry for persistence.
        """
        ...

    def remove_current_topics(
        self,
        broker_id: UUID,
        topics: Collection[str],
    ) -> None: ...

    def remove_current_broker(self, broker_id: UUID) -> None: ...
