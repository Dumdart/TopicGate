from uuid import UUID

from topicgate.core.interfaces.observer_repository import ObserverRepository
from topicgate.core.models.observer_model import ObserverModel
from topicgate.core.models.broker_profile import BrokerProfile


class BrokerRuntimeState:
    """In-memory observer models and repositories, keyed by broker identity."""

    def __init__(self) -> None:
        self._models: dict[UUID, ObserverModel] = {}
        self._repositories: dict[UUID, ObserverRepository] = {}
        self._profile_handles: dict[UUID, BrokerProfile] = {}
        self._config_ids: dict[UUID, int | None] = {}

    def get_model(self, broker_id: UUID) -> ObserverModel | None:
        return self._models.get(broker_id)

    def set_model(self, broker_id: UUID, model: ObserverModel) -> None:
        self._models[broker_id] = model

    def remove(self, broker_id: UUID) -> None:
        self._models.pop(broker_id, None)
        self._repositories.pop(broker_id, None)
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
