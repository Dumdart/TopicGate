from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from topicgate.app.broker_runtime_state import BrokerRuntimeState
from topicgate.app.services.broker_profile_service import BrokerProfileService
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.mqtt_observation import ObservationSource
from topicgate.core.models.topic_message import TopicMessage
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.repository.topic_message_repository import (
    TopicMessageRepository,
)


def test_profile_hydrates_only_its_persisted_topic_states(
    tmp_path: Path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'hydration.db'}")
    initial = BrokerProfileService(database, credential_store=credential_store)
    first = initial.get_profile()
    second = initial.create_profile(
        "Second",
        MqttConfig("second-broker", 1883, "", ""),
    )
    messages = TopicMessageRepository(database)
    first_message = _message(first.id, "factory/temperature", b"21.5", 7)
    second_message = _message(second.id, "factory/temperature", b"18.0", 3)

    try:
        messages.update_message(first_message)
        messages.update_message(second_message)

        restarted = BrokerProfileService(
            database,
            credential_store=credential_store,
            runtime_state=BrokerRuntimeState(),
            topic_messages=messages,
        )

        first_model = restarted.get_profile(first.id).workspace.model
        second_model = restarted.get_profile(second.id).workspace.model

        assert set(first_model.topic_states) == {first_message.topic}
        assert first_model.topic_states[first_message.topic].payload == b"21.5"
        assert first_model.topic_states[first_message.topic].message_count == 7
        assert first_model.topic_states[first_message.topic].recieved_at == (
            first_message.received_at
        )
        assert (
            first_model.topic_states[first_message.topic].source
            is ObservationSource.STORED
        )
        assert (
            first_model.topic_states[first_message.topic].observation_id
            == first_message.observation_id
        )
        assert second_model.topic_states[second_message.topic].payload == b"18.0"
        assert second_model.topic_states[second_message.topic].message_count == 3
    finally:
        messages.close()
        database.dispose()


def test_in_memory_observer_model_takes_precedence_over_hydration(
    tmp_path: Path,
    credential_store,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'runtime-state.db'}")
    initial = BrokerProfileService(database, credential_store=credential_store)
    profile = initial.get_profile()
    messages = TopicMessageRepository(database)
    runtime_state = BrokerRuntimeState()
    runtime_state.set_model(profile.id, profile.workspace.model)
    messages.update_message(_message(profile.id, "cached/topic", b"cached", 1))

    try:
        restarted = BrokerProfileService(
            database,
            credential_store=credential_store,
            runtime_state=runtime_state,
            topic_messages=messages,
        )

        assert restarted.get_profile(profile.id).workspace.model.topic_states == {}
    finally:
        messages.close()
        database.dispose()


def _message(
    broker_id: UUID,
    topic: str,
    payload: bytes,
    message_count: int,
) -> TopicMessage:
    return TopicMessage(
        broker_id=broker_id,
        topic=topic,
        payload=payload,
        qos=1,
        retain=True,
        received_at=datetime.now(timezone.utc),
        payload_size=len(payload),
        message_count=message_count,
        observation_id=uuid4(),
    )
