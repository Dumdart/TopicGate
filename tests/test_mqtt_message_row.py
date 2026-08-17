from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from topicgate.app.services.broker_profile_service import BrokerProfileService
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.database.models.mqtt_message_row import MqttMessageRow


def test_mqtt_message_row_persists_latest_observed_topic_state(
    credential_store,
) -> None:
    database = DatabaseContext("sqlite:///:memory:")
    broker_id = BrokerProfileService(
        database, credential_store=credential_store
    ).get_profile().id
    observation_id = uuid4()
    received_at = datetime.now(timezone.utc)
    row = MqttMessageRow(
        broker_id=broker_id,
        topic="sensors/temperature",
        payload=b"21.5",
        qos=1,
        retain=True,
        received_at=received_at,
        payload_size=4,
        message_count=3,
        observation_id=observation_id,
    )

    with database.transaction() as session:
        session.add(row)

    with database.session() as session:
        persisted = session.scalar(select(MqttMessageRow))

    assert persisted is not None
    assert persisted.broker_id == broker_id
    assert persisted.topic == "sensors/temperature"
    assert persisted.payload == b"21.5"
    assert persisted.qos == 1
    assert persisted.retain is True
    assert persisted.received_at == received_at.replace(tzinfo=None)
    assert persisted.payload_size == 4
    assert persisted.message_count == 3
    assert persisted.observation_id == observation_id
    assert tuple(MqttMessageRow.__table__.primary_key.columns.keys()) == (
        "broker_id",
        "topic",
    )

    database.dispose()
