from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from topicgate.app.services.broker_inspection_service import BrokerInspectionService
from topicgate.app.services.broker_resolver import BrokerResolver
from topicgate.core.models.observation_cache_administration import (
    BrokerCacheUsage,
    CacheUsageSummary,
)
from topicgate.core.models.subscription import Subscription


def test_inspection_composes_passive_broker_reads_without_snapshot() -> None:
    broker = SimpleNamespace(id=uuid4(), name="Primary")
    runtime = MagicMock()
    runtime.list_brokers.return_value = (broker,)
    runtime.get_connection_status.return_value = "connected"
    runtime.get_dropped_message_count.return_value = 3
    runtime.get_topic_update_interval.return_value = 0.2
    runtime.list_subscriptions.return_value = (Subscription("factory/#"),)
    cache = BrokerCacheUsage(broker.id, 4, 128, None, None)
    runtime.get_observation_storage_summary.return_value = CacheUsageSummary((cache,))
    snapshot_service = MagicMock()
    service = BrokerInspectionService(
        runtime,
        snapshot_service,
        BrokerResolver(runtime),
    )

    result = service.inspect(" primary ")

    assert result.identity is broker
    assert result.connection.status == "connected"
    assert result.connection.dropped_message_count == 3
    assert result.subscriptions == (Subscription("factory/#"),)
    assert result.cache == cache
    assert result.snapshot is None
    snapshot_service.build_current.assert_not_called()


def test_inspection_builds_an_explicitly_bounded_snapshot() -> None:
    broker = SimpleNamespace(id=uuid4(), name="Primary")
    runtime = MagicMock()
    runtime.list_brokers.return_value = (broker,)
    runtime.list_subscriptions.return_value = ()
    runtime.get_observation_storage_summary.return_value = CacheUsageSummary(())
    snapshot_service = MagicMock()
    snapshot_service.build_current.return_value = MagicMock(name="snapshot")
    service = BrokerInspectionService(
        runtime,
        snapshot_service,
        BrokerResolver(runtime),
    )

    result = service.inspect(
        broker.id,
        include_snapshot=True,
        snapshot_limit=12,
        payload_limit_bytes=256,
    )

    assert result.snapshot is snapshot_service.build_current.return_value
    snapshot_service.build_current.assert_called_once_with(
        broker.id,
        result_limit=12,
        payload_limit_bytes=256,
    )
    assert result.cache == BrokerCacheUsage(broker.id, 0, 0, None, None)
