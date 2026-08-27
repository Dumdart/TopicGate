from abc import ABC, abstractmethod
from uuid import UUID

from topicgate.core.models.observation_status import ObservationStatus
from topicgate.core.models.topic_message import TopicMessage


class CurrentTopicReader(ABC):
    """Read the unified current state for broker topics."""

    @abstractmethod
    def get_latest_messages(self, broker_id: UUID) -> tuple[TopicMessage, ...]:
        """Return the current live and cached topic states for a broker."""

    @abstractmethod
    def get_observation_status(self, observation_id: UUID) -> ObservationStatus:
        """Return whether a current observation is live or cached."""
