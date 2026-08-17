from abc import ABC, abstractmethod
from uuid import UUID

from topicgate.core.models.topic_message import TopicMessage


class TopicMessageStore(ABC):
    """Read and persist the latest observed state for broker topics."""

    @abstractmethod
    def get_latest_messages(self, broker_id: UUID) -> tuple[TopicMessage, ...]:
        """Return the latest stored state for each topic owned by a broker."""

