from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from topicgate.app.services.broker_profile_service import BrokerProfileService
from topicgate.core.models.message_filter import MessageFilter
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
                after=received_at,
                before=received_at + timedelta(seconds=1),
                topics=(first.topic,),
            )
        ) == (first,)

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
