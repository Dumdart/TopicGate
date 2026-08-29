from uuid import UUID

from topicgate.app.models.broker_inspection import (
    BrokerConnectionState,
    BrokerInspection,
)
from topicgate.app.services.broker_resolver import BrokerResolver
from topicgate.app.services.broker_snapshot_service import (
    DEFAULT_SNAPSHOT_RESULT_LIMIT,
    BrokerSnapshotService,
)
from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.core.models.observation_cache_administration import BrokerCacheUsage
from topicgate.core.payload_limits import MAX_RENDERED_PAYLOAD_BYTES


class BrokerInspectionService:
    """Compose passive broker reads into one presentation-neutral response."""

    def __init__(
        self,
        runtime: TopicGateRuntime,
        snapshot_service: BrokerSnapshotService,
        resolver: BrokerResolver,
    ) -> None:
        self._runtime = runtime
        self._snapshot_service = snapshot_service
        self._resolver = resolver

    def inspect(
        self,
        broker: UUID | str,
        *,
        include_snapshot: bool = False,
        snapshot_limit: int = DEFAULT_SNAPSHOT_RESULT_LIMIT,
        payload_limit_bytes: int = MAX_RENDERED_PAYLOAD_BYTES,
    ) -> BrokerInspection:
        resolved = self._resolver.resolve(broker)
        cache_summary = self._runtime.get_observation_storage_summary(resolved.id)
        cache = next(
            iter(cache_summary.brokers),
            BrokerCacheUsage(resolved.id, 0, 0, None, None),
        )
        snapshot = (
            self._snapshot_service.build_current(
                resolved.id,
                result_limit=snapshot_limit,
                payload_limit_bytes=payload_limit_bytes,
            )
            if include_snapshot
            else None
        )
        return BrokerInspection(
            identity=resolved,
            connection=BrokerConnectionState(
                status=str(self._runtime.get_connection_status(resolved.id)),
                dropped_message_count=self._runtime.get_dropped_message_count(
                    resolved.id
                ),
                topic_update_interval=self._runtime.get_topic_update_interval(
                    resolved.id
                ),
            ),
            subscriptions=self._runtime.list_subscriptions(resolved.id),
            cache=cache,
            snapshot=snapshot,
        )
