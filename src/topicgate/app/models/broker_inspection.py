from dataclasses import dataclass

from topicgate.app.models.broker_snapshot import BrokerSnapshot
from topicgate.core.models.broker_summary import BrokerSummary
from topicgate.core.models.observation_cache_administration import BrokerCacheUsage
from topicgate.core.models.subscription import Subscription


@dataclass(frozen=True)
class BrokerConnectionState:
    status: str
    dropped_message_count: int
    topic_update_interval: float


@dataclass(frozen=True)
class BrokerInspection:
    identity: BrokerSummary
    connection: BrokerConnectionState
    subscriptions: tuple[Subscription, ...]
    cache: BrokerCacheUsage
    snapshot: BrokerSnapshot | None
