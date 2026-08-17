from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from topicgate.app.services.broker_profile_service import BrokerProfileService
from topicgate.app.services.observation_cache_service import ObservationCacheService
from topicgate.core.models.observation_cache_administration import (
    RetentionRemovalReason,
)
from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)
from topicgate.core.models.subscription import Subscription
from topicgate.core.models.topic_message import TopicMessage
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.repository.topic_message_repository import (
    TopicMessageRepository,
)
from topicgate.presentation.retention_presentation import (
    AgeUnit,
    ByteUnit,
    RETENTION_PRESETS,
    cache_usage_display,
    display_age_value,
    display_byte_value,
    exact_age_seconds,
    exact_byte_value,
)


def test_retention_presets_and_lossless_unit_round_trips() -> None:
    assert [item.name for item in RETENTION_PRESETS] == [
        "Conservative",
        "Balanced",
        "Extended",
    ]
    assert RETENTION_PRESETS[0].policy.auto_remove_unsubscribed
    assert not RETENTION_PRESETS[1].policy.auto_remove_unsubscribed
    assert exact_byte_value(64, ByteUnit.KIB) == 64 * 1024
    assert display_byte_value(64 * 1024) == (64, ByteUnit.KIB)
    assert display_byte_value(65_537) == (65_537, ByteUnit.BYTES)
    assert exact_age_seconds(7, AgeUnit.DAYS) == 7 * 86400
    assert display_age_value(91) == (91, AgeUnit.SECONDS)


def test_policy_validates_database_payload_relationship() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        ObservationRetentionPolicy(
            max_payload_bytes_per_topic=1,
            max_payload_bytes_per_broker=3,
            max_persisted_payload_database_bytes_total=2,
        )


def test_usage_and_exact_id_partial_deletion(tmp_path, credential_store) -> None:
    database, messages, service, broker_id = _service(
        tmp_path,
        credential_store,
    )
    original = _message(broker_id, "home/value", b"old")
    try:
        messages.update_message(original)
        usage = service.get_cache_usage().brokers[0]
        display = cache_usage_display(
            usage,
            ObservationRetentionPolicy(max_entries_per_broker=1),
        )
        assert usage.entry_count == 1
        assert usage.stored_payload_bytes == 3
        assert display.entry_warning

        preview = service.preview_clear_cache(broker_id)
        replacement = replace(
            original,
            observation_id=uuid4(),
            payload=b"replacement",
            received_at=original.received_at + timedelta(seconds=1),
        )
        messages.update_message(replacement)
        result = service.confirm_deletion_detailed(preview)

        assert result.deleted_count == 0
        assert result.skipped_count == 1
        assert result.is_partial
        assert messages.get_latest_messages(broker_id) == (replacement,)
    finally:
        messages.close()
        database.dispose()


def test_policy_preview_groups_expired_and_unsubscribed_entries(
    tmp_path,
    credential_store,
) -> None:
    database, messages, service, broker_id = _service(
        tmp_path,
        credential_store,
    )
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    expired = _message(
        broker_id,
        "home/old",
        b"old",
        received_at=now - timedelta(days=2),
    )
    unsubscribed = _message(
        broker_id,
        "garage/current",
        b"new",
        received_at=now,
    )
    try:
        messages.update_message(expired)
        messages.update_message(unsubscribed)
        policy = replace(
            ObservationRetentionPolicy(),
            max_age_seconds=86400,
            auto_remove_unsubscribed=True,
        )

        preview = service.preview_retention_policy(
            policy,
            {broker_id: (Subscription("home/#"),)},
            now=now,
        )

        assert preview.has_deletions
        assert {group.reason for group in preview.groups} == {
            RetentionRemovalReason.EXPIRED,
            RetentionRemovalReason.UNSUBSCRIBED,
        }
        assert preview.deletion.total_entries == 2
    finally:
        messages.close()
        database.dispose()


def test_stale_policy_preview_is_rejected_before_policy_persistence(
    tmp_path,
    credential_store,
) -> None:
    database, messages, service, broker_id = _service(
        tmp_path,
        credential_store,
    )
    first = _message(broker_id, "home/first", b"1")
    second = _message(
        broker_id,
        "home/second",
        b"2",
        received_at=first.received_at + timedelta(seconds=1),
    )
    policy = replace(
        ObservationRetentionPolicy(),
        max_entries_per_broker=1,
    )
    try:
        messages.update_message(first)
        messages.update_message(second)
        preview = service.preview_retention_policy(
            policy,
            {broker_id: (Subscription("home/#"),)},
        )
        messages.update_message(
            replace(
                first,
                observation_id=uuid4(),
                received_at=second.received_at + timedelta(seconds=1),
            )
        )

        with pytest.raises(ValueError, match="preview again"):
            service.confirm_retention_policy(
                preview,
                {broker_id: (Subscription("home/#"),)},
            )

        assert service.get_retention_policy() == ObservationRetentionPolicy()
    finally:
        messages.close()
        database.dispose()


def _service(tmp_path, credential_store):
    database = DatabaseContext(f"sqlite:///{tmp_path / f'{uuid4()}.db'}")
    broker_id = BrokerProfileService(
        database,
        credential_store=credential_store,
    ).get_profile().id
    policies = _Policies()
    messages = TopicMessageRepository(database, policy_provider=policies.get)
    return database, messages, ObservationCacheService(messages, policies), broker_id


class _Policies:
    def __init__(self) -> None:
        self.policy = ObservationRetentionPolicy()

    def get(self) -> ObservationRetentionPolicy:
        return self.policy

    def update(
        self,
        policy: ObservationRetentionPolicy,
    ) -> ObservationRetentionPolicy:
        self.policy = policy
        return policy


def _message(
    broker_id,
    topic: str,
    payload: bytes,
    *,
    received_at: datetime | None = None,
) -> TopicMessage:
    return TopicMessage(
        broker_id=broker_id,
        topic=topic,
        payload=payload,
        qos=0,
        retain=False,
        received_at=received_at or datetime.now(timezone.utc),
        payload_size=len(payload),
        message_count=1,
        observation_id=uuid4(),
    )
