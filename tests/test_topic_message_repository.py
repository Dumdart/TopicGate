from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from topicgate.core.models.message_filter import MessageFilter
from topicgate.core.models.topic_message import TopicMessage
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.repository.topic_message_repository import (
    TopicMessageRepository,
)


def test_topic_message_repository_maps_dtos_and_supports_crud(tmp_path) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'messages.db'}")
    repository = TopicMessageRepository(database)
    received_at = datetime.now(timezone.utc)
    first = _message("home/temperature", received_at)
    second = _message("home/humidity", received_at + timedelta(seconds=1))

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
        database.dispose()


def test_get_latest_message_raises_when_repository_is_empty(tmp_path) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'empty.db'}")
    try:
        with pytest.raises(KeyError, match="latest message"):
            TopicMessageRepository(database).get_latest_message()
    finally:
        database.dispose()


def _message(topic: str, received_at: datetime) -> TopicMessage:
    payload = b"21.5"
    return TopicMessage(
        broker_id=uuid4(),
        topic=topic,
        payload=payload,
        qos=1,
        retain=False,
        received_at=received_at,
        payload_size=len(payload),
        message_count=1,
        observation_id=uuid4(),
    )
