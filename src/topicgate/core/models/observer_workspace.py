from dataclasses import dataclass
from uuid import UUID

from topicgate.core.models.observer_model import ObserverModel
from topicgate.core.models.subscription import Subscription


@dataclass
class ObserverWorkspace:
    id: UUID
    profile_id: UUID
    model: ObserverModel
    subscriptions: tuple[Subscription, ...] = ()
