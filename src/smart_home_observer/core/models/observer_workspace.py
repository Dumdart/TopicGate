from dataclasses import dataclass
from uuid import UUID

from smart_home_observer.core.models.observer_model import ObserverModel


@dataclass
class ObserverWorkspace:
    id: UUID
    profile_id: UUID
    model: ObserverModel
