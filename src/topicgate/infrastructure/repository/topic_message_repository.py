from queue import Queue
from threading import Lock, Thread
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

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
        self._write_queue: Queue[
            tuple[Literal["create", "update"], TopicMessage] | None
        ] = Queue()
        self._error_lock = Lock()
        self._write_error: BaseException | None = None
        self._closed = False
        self._writer = Thread(
            target=self._process_writes,
            name="topic-message-writer",
            daemon=True,
        )
        self._writer.start()

    def get_message(self, message_id: UUID) -> TopicMessage:
        self.flush()
        with self._db.session() as session:
            row = session.scalar(
                select(MqttMessageRow).where(
                    MqttMessageRow.observation_id == message_id
                )
            )
            if row is None:
                raise KeyError(f"Unknown topic message: {message_id}")
            return TopicMessageMapper.to_dto(row)

    def get_latest_message(self, topic: str | None = None) -> TopicMessage:
        self.flush()
        statement = select(MqttMessageRow).order_by(
            MqttMessageRow.received_at.desc()
        )
        if topic is not None:
            statement = statement.where(MqttMessageRow.topic == topic)
        with self._db.session() as session:
            row = session.scalar(statement.limit(1))
            if row is None:
                raise KeyError("Unknown topic message: latest message")
            return TopicMessageMapper.to_dto(row)

    def get_all_latest_messages(self) -> list[tuple[str, TopicMessage]]:
        self.flush()
        ranked_messages = select(
            MqttMessageRow,
            func.row_number()
            .over(
                partition_by=MqttMessageRow.topic,
                order_by=MqttMessageRow.received_at.desc(),
            )
            .label("message_rank"),
        ).subquery()
        latest_message = aliased(MqttMessageRow, ranked_messages)
        statement = (
            select(latest_message)
            .where(ranked_messages.c.message_rank == 1)
            .order_by(latest_message.topic)
        )

        with self._db.session() as session:
            return [
                (row.topic, TopicMessageMapper.to_dto(row))
                for row in session.scalars(statement).all()
            ]

    def search_message(
        self, message_filter: MessageFilter
    ) -> tuple[TopicMessage, ...]:
        self.flush()
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
        self._enqueue("create", message)
        return message

    def update_message(self, message: TopicMessage) -> TopicMessage:
        self._enqueue("update", message)
        return message

    def delete_message(self, message_id: UUID) -> TopicMessage:
        self.flush()
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

    def flush(self) -> None:
        """Wait until all queued writes have completed."""
        self._write_queue.join()
        with self._error_lock:
            error = self._write_error
            self._write_error = None
        if error is not None:
            raise RuntimeError("A queued topic message write failed.") from error

    def close(self) -> None:
        """Drain queued writes and stop the database writer."""
        if self._closed:
            return
        self.flush()
        self._closed = True
        self._write_queue.put(None)
        self._writer.join()

    def _enqueue(
        self,
        operation: Literal["create", "update"],
        message: TopicMessage,
    ) -> None:
        if self._closed:
            raise RuntimeError("Topic message repository is closed.")
        self._write_queue.put_nowait((operation, message))

    def _process_writes(self) -> None:
        while True:
            item = self._write_queue.get()
            try:
                if item is None:
                    return
                operation, message = item
                with self._db.session() as session:
                    row = TopicMessageMapper.to_row(message)
                    if operation == "create":
                        session.add(row)
                    else:
                        session.merge(row)
                    session.commit()
            except BaseException as error:
                # Check the failure on the caller's next consistency barrier.
                with self._error_lock:
                    if self._write_error is None:
                        self._write_error = error
            finally:
                self._write_queue.task_done()
