from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import MagicMock

from topicgate.app.services.observation_cache_service import ObservationCacheService
from topicgate.core.models.subscription import Subscription
from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)
from topicgate.core.models.topic_message import TopicMessage
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.repository.topic_message_repository import (
    TopicMessageRepository,
)


def test_unsubscribed_preview_and_confirm_delete_only_unmatched_entries(
    tmp_path,
    credential_store,
) -> None:
    from topicgate.app.services.broker_profile_service import BrokerProfileService

    database = DatabaseContext(f"sqlite:///{tmp_path / 'cache-service.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    messages = TopicMessageRepository(database)
    policies = _Policies()
    service = ObservationCacheService(messages, policies)
    kept = _message(broker_id, "home/temperature")
    removed = _message(broker_id, "garage/door")

    try:
        messages.update_message(kept)
        messages.update_message(removed)

        preview = service.preview_unsubscribed(
            broker_id,
            (Subscription("home/#"),),
        )

        assert tuple(entry.topic for entry in preview.entries) == ("garage/door",)
        assert preview.total_entries == 1
        assert preview.stored_payload_bytes == len(removed.payload)
        assert service.confirm_deletion(preview) == 1
        assert tuple(
            current.message for current in messages.get_current_topics(broker_id)
        ) == (kept,)
    finally:
        messages.close()
        database.dispose()


def test_policy_update_is_persisted_before_enforcing_new_limits() -> None:
    messages = MagicMock()
    policies = MagicMock()
    policy = ObservationRetentionPolicy(max_entries_per_broker=500)
    policies.update.return_value = policy
    service = ObservationCacheService(messages, policies)

    assert service.update_retention_policy(policy) is policy
    policies.update.assert_called_once_with(policy)
    messages.enforce_retention.assert_called_once_with()


def test_flush_pending_writes_delegates_to_message_repository() -> None:
    messages = MagicMock()
    service = ObservationCacheService(messages, MagicMock())

    service.flush_pending_writes()

    messages.flush.assert_called_once_with()


class _Policies:
    def get(self):
        raise AssertionError("Policy reads are not needed for deletion previews.")

    def update(self, policy):
        return policy


def _message(broker_id, topic: str) -> TopicMessage:
    payload = b"value"
    return TopicMessage(
        broker_id=broker_id,
        topic=topic,
        payload=payload,
        qos=0,
        retain=False,
        received_at=datetime.now(timezone.utc),
        payload_size=len(payload),
        message_count=1,
        observation_id=uuid4(),
    )
