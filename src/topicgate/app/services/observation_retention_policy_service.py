from threading import Lock

from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)
from topicgate.infrastructure.repository.observation_retention_policy_repository import (
    ObservationRetentionPolicyRepository,
)


class ObservationRetentionPolicyService:
    """Keep the persisted retention policy available without callback I/O."""

    def __init__(
        self,
        repository: ObservationRetentionPolicyRepository,
    ) -> None:
        self._repository = repository
        self._lock = Lock()
        self._policy = repository.get()

    def get(self) -> ObservationRetentionPolicy:
        with self._lock:
            return self._policy

    def update(
        self,
        policy: ObservationRetentionPolicy,
    ) -> ObservationRetentionPolicy:
        persisted = self._repository.update(policy)
        with self._lock:
            self._policy = persisted
        return persisted
