from uuid import UUID

from topicgate.core.interfaces.observer_repository import ObserverRepository
from topicgate.core.models.broker_profile import BrokerProfile


class BrokerRuntimeState:
    """In-memory repositories and profile metadata, keyed by broker identity."""

    def __init__(self) -> None:
        self._repositories: dict[UUID, ObserverRepository] = {}
        self._profile_handles: dict[UUID, BrokerProfile] = {}
        self._config_ids: dict[UUID, int | None] = {}

    def remove_profile_metadata(self, broker_id: UUID) -> None:
        """Forget cached profile data without changing runtime repositories."""
        self._profile_handles.pop(broker_id, None)
        self._config_ids.pop(broker_id, None)

    def get_config_id(self, broker_id: UUID, persisted_id: int | None) -> int | None:
        return self._config_ids.get(broker_id, persisted_id)

    def set_config_id(self, broker_id: UUID, config_id: int | None) -> None:
        self._config_ids[broker_id] = config_id

    def get_profile_handle(self, broker_id: UUID) -> BrokerProfile | None:
        return self._profile_handles.get(broker_id)

    def set_profile_handle(self, profile: BrokerProfile) -> None:
        self._profile_handles[profile.id] = profile

    @property
    def repositories(self) -> dict[UUID, ObserverRepository]:
        return self._repositories
