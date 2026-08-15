from uuid import UUID

from sqlalchemy import select

from topicgate.core.models.message_filter import MessageFilter
from topicgate.core.models.topic_message import TopicMessage
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.database.mappers.topic_message_mapper import (
    TopicMessageMapper,
)
from topicgate.infrastructure.database.models.mqtt_message_row import MqttMessageRow


class TopicMessageRepository:
    """Persist the latest observed MQTT message for each broker topic."""

    def __init__(self, db: DatabaseContext) -> None:
        self._db = db

    def get_message(self, message_id: UUID) -> TopicMessage:
        with self._db.session() as session:
            row = session.scalar(
                select(MqttMessageRow).where(
                    MqttMessageRow.observation_id == message_id
                )
            )
            if row is None:
                raise KeyError(f"Unknown topic message: {message_id}")
            return TopicMessageMapper.to_dto(row)

    def get_latest_message(self) -> TopicMessage:
        with self._db.session() as session:
            row = session.scalar(
                select(MqttMessageRow)
                .order_by(MqttMessageRow.received_at.desc())
                .limit(1)
            )
            if row is None:
                raise KeyError("Unknown topic message: latest message")
            return TopicMessageMapper.to_dto(row)

    def search_message(
        self, message_filter: MessageFilter
    ) -> tuple[TopicMessage, ...]:
        statement = select(MqttMessageRow)
        if message_filter.after is not None:
            statement = statement.where(
                MqttMessageRow.received_at >= message_filter.after
            )
        if message_filter.before is not None:
            statement = statement.where(
                MqttMessageRow.received_at <= message_filter.before
            )
        if message_filter.topics:
            statement = statement.where(
                MqttMessageRow.topic.in_(message_filter.topics)
            )
        statement = statement.order_by(MqttMessageRow.received_at.desc())

        with self._db.session() as session:
            return tuple(
                TopicMessageMapper.to_dto(row)
                for row in session.scalars(statement).all()
            )

    def create_message(self, message: TopicMessage) -> TopicMessage:
        with self._db.session() as session:
            row = TopicMessageMapper.to_row(message)
            session.add(row)
            session.commit()
            return TopicMessageMapper.to_dto(row)

    def update_message(self, message: TopicMessage) -> TopicMessage:
        with self._db.session() as session:
            row = session.merge(TopicMessageMapper.to_row(message))
            session.commit()
            return TopicMessageMapper.to_dto(row)

    def delete_message(self, message_id: UUID) -> TopicMessage:
        with self._db.session() as session:
            row = session.scalar(
                select(MqttMessageRow).where(
                    MqttMessageRow.observation_id == message_id
                )
            )
            if row is None:
                raise KeyError(f"Unknown topic message: {message_id}")
            message = TopicMessageMapper.to_dto(row)
            session.delete(row)
            session.commit()
            return message
