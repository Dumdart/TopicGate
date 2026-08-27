from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from topicgate.app.services.broker_profile_service import BrokerProfileService
from topicgate.core.models.message_filter import MessageFilter, OrderType
from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)
from topicgate.core.models.topic_message import TopicMessage
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.repository.topic_message_repository import (
    TopicMessageRepository,
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


def test_get_all_latest_messages_returns_latest_message_per_topic(
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

        assert repository.get_all_latest_messages() == [
            (humidity.topic, humidity),
            (newer.topic, newer),
        ]
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

        assert repository.get_latest_messages(first_broker) == (first,)
        assert repository.get_latest_messages(second_broker) == (second,)
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

        stored = repository.get_latest_messages(broker_id)

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

        assert repository.get_latest_messages(broker_id) == ()
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
        assert repository.get_latest_messages(broker_id) == (replacement,)
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

        assert tuple(
            message.topic for _, message in repository.get_all_latest_messages()
        ) == ("middle", "newest")
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

        assert tuple(
            message.topic for message in repository.get_latest_messages(broker_id)
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

        assert tuple(
            message.topic for _, message in repository.get_all_latest_messages()
        ) == ("new",)
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
