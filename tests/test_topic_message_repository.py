from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event
from uuid import uuid4

import pytest

from topicgate.app.services.broker_profile_service import BrokerProfileService
from topicgate.core.models.current_topic import CurrentTopic
from topicgate.core.models.message_filter import MessageFilter, OrderType
from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)
from topicgate.core.models.observation_status import ObservationStatus
from topicgate.core.models.topic_message import TopicMessage
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.repository.topic_message_repository import (
    TopicMessageRepository,
)
from topicgate.infrastructure.database.mappers.topic_message_mapper import (
    TopicMessageMapper,
)


def test_topic_message_repository_maps_dtos_and_supports_crud(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'messages.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    repository = TopicMessageRepository(database)
    received_at = datetime.now(timezone.utc)
    first = _message(broker_id, "home/temperature", received_at)
    second = _message(
        broker_id,
        "home/humidity",
        received_at + timedelta(seconds=1),
    )

    try:
        assert repository.create_message(first) == first
        assert repository.create_message(second) == second
        assert repository.get_message(first.observation_id) == first
        assert repository.get_latest_message() == second
        assert repository.search_message(
            MessageFilter(
                broker_id=broker_id,
                after=received_at,
                before=received_at + timedelta(seconds=1),
                topic_filter="home/#",
                limit=2,
            )
        ) == (second, first)

        updated = replace(first, payload=b"22.0", payload_size=4, message_count=2)
        assert repository.update_message(updated) == updated
        assert repository.get_message(first.observation_id) == updated
        assert repository.delete_message(first.observation_id) == updated
        with pytest.raises(KeyError, match="Unknown topic message"):
            repository.get_message(first.observation_id)
    finally:
        repository.close()
        database.dispose()


def test_get_latest_message_raises_when_repository_is_empty(tmp_path) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'empty.db'}")
    repository = TopicMessageRepository(database)
    try:
        with pytest.raises(KeyError, match="latest message"):
            repository.get_latest_message()
    finally:
        repository.close()
        database.dispose()


def test_search_message_rejects_negative_limit(tmp_path) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'negative-limit.db'}")
    repository = TopicMessageRepository(database)

    try:
        with pytest.raises(ValueError, match="cannot be negative"):
            repository.search_message(MessageFilter(broker_id=uuid4(), limit=-1))
    finally:
        repository.close()
        database.dispose()


@pytest.mark.parametrize(
    ("order", "expected_topics"),
    [
        (OrderType.RECEIVED_ASC, ("zeta", "alpha", "middle")),
        (OrderType.RECEIVED_DESC, ("middle", "alpha", "zeta")),
        (OrderType.TOPIC_ASC, ("alpha", "middle", "zeta")),
        (OrderType.TOPIC_DESC, ("zeta", "middle", "alpha")),
        (OrderType.MESSAGE_COUNT_ASC, ("alpha", "zeta", "middle")),
        (OrderType.MESSAGE_COUNT_DESC, ("middle", "zeta", "alpha")),
        (OrderType.PAYLOAD_SIZE_ASC, ("alpha", "middle", "zeta")),
        (OrderType.PAYLOAD_SIZE_DESC, ("zeta", "middle", "alpha")),
    ],
)
def test_search_message_supports_order_types(
    tmp_path,
    credential_store,
    order: OrderType,
    expected_topics: tuple[str, ...],
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'ordered.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    repository = TopicMessageRepository(database)
    received_at = datetime.now(timezone.utc)
    messages = (
        replace(
            _message(broker_id, "zeta", received_at),
            message_count=2,
            payload=b"x" * 30,
            payload_size=30,
        ),
        replace(
            _message(broker_id, "alpha", received_at + timedelta(seconds=1)),
            message_count=1,
            payload=b"x" * 10,
            payload_size=10,
        ),
        replace(
            _message(broker_id, "middle", received_at + timedelta(seconds=2)),
            message_count=3,
            payload=b"x" * 20,
            payload_size=20,
        ),
    )

    try:
        for message in messages:
            repository.create_message(message)

        result = repository.search_message(
            MessageFilter(broker_id=broker_id, order=order)
        )

        assert tuple(message.topic for message in result) == expected_topics
    finally:
        repository.close()
        database.dispose()


def test_queued_writes_are_flushed_in_order(tmp_path, credential_store) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'queued.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    repository = TopicMessageRepository(database)
    message = _message(
        broker_id,
        "home/temperature",
        datetime.now(timezone.utc),
    )
    updated = replace(message, payload=b"22.0", payload_size=4, message_count=2)

    try:
        assert repository.create_message(message) == message
        assert repository.update_message(updated) == updated

        repository.flush()

        assert repository.get_message(message.observation_id) == updated
    finally:
        repository.close()
        database.dispose()


def test_record_message_updates_current_map_and_queues_latest_state(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'recorded.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    repository = TopicMessageRepository(database)
    message = _message(broker_id, "home/temperature", datetime.now(timezone.utc))
    updated = replace(
        message,
        payload=b"22.0",
        payload_size=4,
        message_count=2,
        observation_id=uuid4(),
    )

    try:
        repository.record_message(message)
        repository.record_message(updated)

        assert repository.get_current_topics(broker_id) == (
            CurrentTopic(updated, ObservationStatus.LIVE),
        )
        assert repository.get_message(updated.observation_id) == updated
    finally:
        repository.close()
        database.dispose()


def test_policy_transformation_is_shared_by_current_and_persisted_state(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'canonical.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    policy = ObservationRetentionPolicy(max_payload_bytes_per_topic=4)
    repository = TopicMessageRepository(database, lambda: policy)
    message = replace(
        _message(broker_id, "home/value", datetime.now(timezone.utc)),
        payload=b"123456",
        payload_size=6,
    )

    try:
        repository.record_message(message)

        current = repository.get_current_topic(broker_id, message.topic)
        assert current is not None
        assert current.message.payload == b"1234"
        assert current.message.payload_size == 6
        assert repository.get_message(message.observation_id) == current.message
    finally:
        repository.close()
        database.dispose()


def test_current_topic_read_is_atomic_and_memory_only_while_write_is_queued(
    tmp_path,
    credential_store,
    monkeypatch,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'memory-only.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    repository = TopicMessageRepository(database)
    message = _message(broker_id, "queued/topic", datetime.now(timezone.utc))
    writer_entered = Event()
    release_writer = Event()
    original = TopicMessageMapper.to_row

    def blocked_to_row(entry):
        writer_entered.set()
        assert release_writer.wait(timeout=5)
        return original(entry)

    monkeypatch.setattr(TopicMessageMapper, "to_row", blocked_to_row)
    try:
        repository.record_message(message)
        assert writer_entered.wait(timeout=5)

        assert repository.get_current_topic(
            broker_id, message.topic
        ) == CurrentTopic(message, ObservationStatus.LIVE)
    finally:
        release_writer.set()
        repository.close()
        database.dispose()


def test_live_message_replaces_hydrated_cached_state(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'live-replaces.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    cached = _message(broker_id, "shared/topic", datetime.now(timezone.utc))
    writer = TopicMessageRepository(database)
    writer.update_message(cached)
    writer.close()
    repository = TopicMessageRepository(database)
    live = replace(cached, observation_id=uuid4(), payload=b"live")

    try:
        repository.record_message(live)

        assert repository.get_current_topic(
            broker_id, cached.topic
        ) == CurrentTopic(live, ObservationStatus.LIVE)
    finally:
        repository.close()
        database.dispose()


def test_persisted_deletion_keeps_matching_live_current_state(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'delete-live.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    repository = TopicMessageRepository(database)
    message = _message(broker_id, "live/topic", datetime.now(timezone.utc))

    try:
        repository.update_message(message)
        preview = repository.preview_deletion(broker_id)
        repository.record_message(message)

        assert repository.delete_previewed(preview) == 1
        assert repository.get_current_topic(
            broker_id, message.topic
        ) == CurrentTopic(message, ObservationStatus.LIVE)
    finally:
        repository.close()
        database.dispose()


def test_explicit_topic_and_broker_current_state_eviction(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'eviction.db'}")
    profiles = BrokerProfileService(database, credential_store=credential_store)
    first_broker = profiles.get_profile().id
    second_broker = profiles.create_profile(
        "Second", profiles.get_profile().config
    ).id
    repository = TopicMessageRepository(database)
    now = datetime.now(timezone.utc)
    first = _message(first_broker, "first", now)
    kept = _message(first_broker, "kept", now)
    second = _message(second_broker, "second", now)

    try:
        for message in (first, kept, second):
            repository.record_message(message)

        repository.remove_current_topics(first_broker, (first.topic,))
        assert _current_messages(repository, first_broker) == (kept,)

        repository.remove_current_broker(first_broker)
        assert repository.get_current_topics(first_broker) == ()
        assert _current_messages(repository, second_broker) == (second,)
    finally:
        repository.close()
        database.dispose()


def test_retention_removes_cached_but_not_live_current_state(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'retention-state.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    policy = ObservationRetentionPolicy(
        max_entries_per_broker=1,
        max_entries_total=1,
    )
    repository = TopicMessageRepository(database, lambda: policy)
    now = datetime.now(timezone.utc)
    cached = _message(broker_id, "cached", now)
    live = _message(broker_id, "live", now + timedelta(seconds=1))

    try:
        repository.update_message(cached)
        repository.flush()
        repository.record_message(live)
        repository.flush()

        assert repository.get_current_topics(broker_id) == (
            CurrentTopic(live, ObservationStatus.LIVE),
        )

        older_live = replace(
            cached,
            topic="older-live",
            observation_id=uuid4(),
        )
        repository.record_message(older_live)
        repository.flush()
        assert repository.get_current_topic(
            broker_id, older_live.topic
        ) == CurrentTopic(older_live, ObservationStatus.LIVE)
    finally:
        repository.close()
        database.dispose()


def test_writer_failure_preserves_current_state(
    tmp_path,
    credential_store,
    monkeypatch,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'writer-failure.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    repository = TopicMessageRepository(database)
    message = _message(broker_id, "failed/write", datetime.now(timezone.utc))

    def fail_to_row(_entry):
        raise OSError("write failed")

    monkeypatch.setattr(TopicMessageMapper, "to_row", fail_to_row)
    try:
        repository.record_message(message)
        with pytest.raises(RuntimeError, match="queued topic message write failed"):
            repository.flush()

        assert repository.get_current_topic(
            broker_id, message.topic
        ) == CurrentTopic(message, ObservationStatus.LIVE)
    finally:
        repository.close()
        database.dispose()


def test_repository_hydrates_persisted_messages_as_cached(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'hydrated-current.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    message = _message(broker_id, "cached/topic", datetime.now(timezone.utc))
    writer = TopicMessageRepository(database)
    writer.update_message(message)
    writer.close()

    repository = TopicMessageRepository(database)
    try:
        assert repository.get_current_topics(broker_id) == (
            CurrentTopic(message, ObservationStatus.CACHED),
        )
    finally:
        repository.close()
        database.dispose()


def test_get_messages_is_scoped_to_each_broker(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'latest.db'}")
    profiles = BrokerProfileService(database, credential_store=credential_store)
    broker_id = profiles.get_profile().id
    newer_broker_id = profiles.create_profile(
        "Second",
        profiles.get_profile().config,
    ).id
    repository = TopicMessageRepository(database)
    received_at = datetime.now(timezone.utc)
    older = _message(broker_id, "home/temperature", received_at)
    newer = _message(
        newer_broker_id,
        "home/temperature",
        received_at + timedelta(seconds=1),
    )
    humidity = _message(broker_id, "home/humidity", received_at)

    try:
        repository.create_message(older)
        repository.create_message(newer)
        repository.create_message(humidity)

        assert repository.get_messages(broker_id) == (humidity, older)
        assert repository.get_messages(newer_broker_id) == (newer,)
    finally:
        repository.close()
        database.dispose()


def test_get_latest_messages_is_scoped_to_broker(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'broker-latest.db'}")
    profiles = BrokerProfileService(database, credential_store=credential_store)
    first_broker = profiles.get_profile().id
    second_broker = profiles.create_profile(
        "Second",
        profiles.get_profile().config,
    ).id
    repository = TopicMessageRepository(database)
    received_at = datetime.now(timezone.utc)
    first = _message(first_broker, "shared/topic", received_at)
    second = _message(second_broker, "shared/topic", received_at)

    try:
        repository.update_message(first)
        repository.update_message(second)

        assert _current_messages(repository, first_broker) == (first,)
        assert _current_messages(repository, second_broker) == (second,)
    finally:
        repository.close()
        database.dispose()


def test_repository_truncates_payload_and_evicts_oldest_excess_entries(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'retention.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    policy = ObservationRetentionPolicy(
        max_entries_per_broker=2,
        max_entries_total=2,
        max_payload_bytes_per_topic=4,
        max_payload_bytes_per_broker=8,
        max_persisted_payload_database_bytes_total=8,
    )
    repository = TopicMessageRepository(database, lambda: policy)
    received_at = datetime.now(timezone.utc)

    try:
        repository.update_message(
            replace(
                _message(broker_id, "oldest", received_at),
                payload=b"123456",
                payload_size=6,
            )
        )
        repository.update_message(
            _message(broker_id, "middle", received_at + timedelta(seconds=1))
        )
        repository.update_message(
            _message(broker_id, "newest", received_at + timedelta(seconds=2))
        )
        repository.flush()

        stored = _current_messages(repository, broker_id)

        assert tuple(message.topic for message in stored) == ("middle", "newest")
        assert sum(len(message.payload) for message in stored) == 8
    finally:
        repository.close()
        database.dispose()


def test_repository_automatically_deletes_expired_entries(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'expiry.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    policy = ObservationRetentionPolicy(max_age_seconds=60)
    repository = TopicMessageRepository(database, lambda: policy)

    try:
        repository.update_message(
            _message(
                broker_id,
                "expired",
                datetime.now(timezone.utc) - timedelta(minutes=2),
            )
        )
        repository.flush()

        assert repository.get_current_topics(broker_id) == ()
    finally:
        repository.close()
        database.dispose()


def test_confirmed_deletion_does_not_remove_a_newer_observation(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'preview.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    repository = TopicMessageRepository(database)
    original = _message(broker_id, "home/value", datetime.now(timezone.utc))

    try:
        repository.update_message(original)
        preview = repository.preview_deletion(broker_id)
        replacement = replace(
            original,
            payload=b"new!",
            received_at=original.received_at + timedelta(seconds=1),
            observation_id=uuid4(),
        )
        repository.update_message(replacement)

        assert repository.delete_previewed(preview) == 0
        assert _current_messages(repository, broker_id) == (replacement,)
    finally:
        repository.close()
        database.dispose()


def test_global_limits_evict_oldest_entries_across_brokers(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'global-retention.db'}")
    profiles = BrokerProfileService(database, credential_store=credential_store)
    first_broker = profiles.get_profile().id
    second_broker = profiles.create_profile(
        "Second",
        profiles.get_profile().config,
    ).id
    policy = ObservationRetentionPolicy(
        max_entries_per_broker=2,
        max_entries_total=2,
        max_payload_bytes_per_topic=4,
        max_payload_bytes_per_broker=8,
        max_persisted_payload_database_bytes_total=8,
    )
    repository = TopicMessageRepository(database, lambda: policy)
    received_at = datetime.now(timezone.utc)

    try:
        repository.update_message(
            _message(first_broker, "oldest", received_at)
        )
        repository.update_message(
            _message(
                second_broker,
                "middle",
                received_at + timedelta(seconds=1),
            )
        )
        repository.update_message(
            _message(
                first_broker,
                "newest",
                received_at + timedelta(seconds=2),
            )
        )

        stored = repository.get_messages(first_broker) + repository.get_messages(
            second_broker
        )
        assert tuple(message.topic for message in stored) == ("newest", "middle")
    finally:
        repository.close()
        database.dispose()


def test_per_broker_payload_limit_evicts_oldest_entry(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'broker-bytes.db'}")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    policy = ObservationRetentionPolicy(
        max_entries_per_broker=10,
        max_entries_total=10,
        max_payload_bytes_per_topic=4,
        max_payload_bytes_per_broker=5,
        max_persisted_payload_database_bytes_total=100,
    )
    repository = TopicMessageRepository(database, lambda: policy)
    received_at = datetime.now(timezone.utc)

    try:
        repository.update_message(_message(broker_id, "old", received_at))
        repository.update_message(
            _message(broker_id, "new", received_at + timedelta(seconds=1))
        )
        repository.flush()

        assert tuple(
            message.topic for message in _current_messages(repository, broker_id)
        ) == ("new",)
    finally:
        repository.close()
        database.dispose()


def test_global_payload_limit_evicts_oldest_entry_across_brokers(
    tmp_path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'global-bytes.db'}")
    profiles = BrokerProfileService(database, credential_store=credential_store)
    first_broker = profiles.get_profile().id
    second_broker = profiles.create_profile(
        "Second",
        profiles.get_profile().config,
    ).id
    policy = ObservationRetentionPolicy(
        max_entries_per_broker=10,
        max_entries_total=10,
        max_payload_bytes_per_topic=4,
        max_payload_bytes_per_broker=5,
        max_persisted_payload_database_bytes_total=6,
    )
    repository = TopicMessageRepository(database, lambda: policy)
    received_at = datetime.now(timezone.utc)

    try:
        repository.update_message(_message(first_broker, "old", received_at))
        repository.update_message(
            _message(
                second_broker,
                "new",
                received_at + timedelta(seconds=1),
            )
        )

        stored = repository.get_messages(first_broker) + repository.get_messages(
            second_broker
        )
        assert tuple(message.topic for message in stored) == ("new",)
    finally:
        repository.close()
        database.dispose()


def _message(broker_id, topic: str, received_at: datetime) -> TopicMessage:
    payload = b"21.5"
    return TopicMessage(
        broker_id=broker_id,
        topic=topic,
        payload=payload,
        qos=1,
        retain=False,
        received_at=received_at,
        payload_size=len(payload),
        message_count=1,
        observation_id=uuid4(),
    )


def _current_messages(
    repository: TopicMessageRepository,
    broker_id,
) -> tuple[TopicMessage, ...]:
    return tuple(
        current.message for current in repository.get_current_topics(broker_id)
    )
