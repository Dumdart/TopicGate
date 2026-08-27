from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from topicgate.app.services.observation_query_service import ObservationQueryService
from topicgate.core.interfaces.stored_observation_reader import StoredObservationReader
from topicgate.core.models.message_filter import MessageFilter
from topicgate.core.models.observation_cache_administration import (
    BrokerCacheUsage,
    CacheUsageSummary,
)
from topicgate.core.models.observation_deletion_preview import (
    ObservationDeletionEntry,
    ObservationDeletionPreview,
)
from topicgate.core.models.subscription import Subscription
from topicgate.core.models.topic_message import TopicMessage


def test_query_service_delegates_observation_reads() -> None:
    reader = MagicMock(spec=StoredObservationReader)
    service = ObservationQueryService(reader)
    message_id = uuid4()
    broker_id = uuid4()
    message_filter = MessageFilter(broker_id=broker_id)
    message = MagicMock(spec=TopicMessage)
    usage = CacheUsageSummary((BrokerCacheUsage(broker_id, 1, 2, None, None),))
    reader.get_message.return_value = message
    reader.get_messages.return_value = (message,)
    reader.get_latest_message.return_value = message
    reader.search_message.return_value = (message,)
    reader.cache_usage.return_value = usage

    assert service.get_message(message_id) is message
    assert service.get_broker_messages(broker_id) == (message,)
    assert service.get_latest_message() is message
    assert service.query_stored_observations(message_filter) == (message,)
    assert service.get_cache_usage() is usage

    reader.get_message.assert_called_once_with(message_id)
    reader.get_messages.assert_called_once_with(broker_id)
    reader.get_latest_message.assert_called_once_with(None)
    reader.search_message.assert_called_once_with(message_filter)
    reader.cache_usage.assert_called_once_with()


def test_query_service_maps_persisted_topics_to_subscription_status() -> None:
    reader = MagicMock(spec=StoredObservationReader)
    service = ObservationQueryService(reader)
    broker_id = uuid4()
    subscribed = ObservationDeletionEntry(
        broker_id,
        "home/temperature",
        uuid4(),
        datetime.now(timezone.utc),
        3,
    )
    unsubscribed = ObservationDeletionEntry(
        broker_id,
        "garage/door",
        uuid4(),
        datetime.now(timezone.utc),
        4,
    )
    reader.preview_deletion.return_value = ObservationDeletionPreview(
        broker_id, (subscribed, unsubscribed)
    )

    result = service.get_persisted_topics(broker_id, (Subscription("home/#"),))

    assert tuple(item.topic for item in result) == (
        "home/temperature",
        "garage/door",
    )
    assert tuple(item.is_subscribed for item in result) == (True, False)
    reader.preview_deletion.assert_called_once_with(broker_id)
