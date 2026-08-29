from dataclasses import dataclass
from uuid import UUID

from topicgate.core.models.subscription import Subscription


@dataclass
class ObserverWorkspace:
    id: UUID
    profile_id: UUID
    subscriptions: tuple[Subscription, ...] = ()
