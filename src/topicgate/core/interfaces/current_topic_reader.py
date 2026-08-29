from typing import Protocol
from uuid import UUID

from topicgate.core.models.current_topic import CurrentTopic


class CurrentTopicReader(Protocol):
    """Read the unified current state for broker topics."""

    def get_current_topics(self, broker_id: UUID) -> tuple[CurrentTopic, ...]:
        """Return atomic current topic snapshots for a broker."""
        ...

    def get_current_topic(
        self,
        broker_id: UUID,
        topic: str,
    ) -> CurrentTopic | None:
        """Return one atomic current topic snapshot when present."""
        ...
