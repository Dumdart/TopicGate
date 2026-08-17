from collections.abc import Callable, Collection
from datetime import datetime, timedelta, timezone
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Literal
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased

from topicgate.core.models.message_filter import MessageFilter
from topicgate.core.models.observation_deletion_preview import (
    ObservationDeletionEntry,
    ObservationDeletionPreview,
)
from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)
from topicgate.core.models.topic_message import TopicMessage
from topicgate.core.interfaces.topic_message_store import TopicMessageStore
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.database.mappers.topic_message_mapper import (
    TopicMessageMapper,
)
from topicgate.infrastructure.database.models.mqtt_message_row import MqttMessageRow
from topicgate.processors.observation_retention_processor import (
    ObservationRetentionProcessor,
)


class TopicMessageRepository(TopicMessageStore):
    """Persist the latest observed MQTT message for each broker topic."""

    _MAX_WRITE_BATCH = 100

    def __init__(
        self,
        db: DatabaseContext,
        policy_provider: Callable[[], ObservationRetentionPolicy] | None = None,
    ) -> None:
        self._db = db
        self._policy_provider = policy_provider
        self._write_queue: Queue[
            tuple[Literal["create", "update"], TopicMessage] | None
        ] = Queue()
        self._error_lock = Lock()
        self._write_error: BaseException | None = None
        self._closed = False
        if self._policy_provider is not None:
            self._enforce_retention(self._policy_provider())
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

    def get_latest_messages(self, broker_id: UUID) -> tuple[TopicMessage, ...]:
        """Return the current persisted topic states for one broker."""
        self.flush()
        statement = (
            select(MqttMessageRow)
            .where(MqttMessageRow.broker_id == broker_id)
            .order_by(MqttMessageRow.topic)
        )
        with self._db.session() as session:
            return tuple(
                TopicMessageMapper.to_dto(row)
                for row in session.scalars(statement).all()
            )

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

    def preview_deletion(
        self,
        broker_id: UUID,
        topics: Collection[str] | None = None,
    ) -> ObservationDeletionPreview:
        """Describe exact persisted observations without deleting them."""
        self.flush()
        statement = (
            select(MqttMessageRow)
            .where(MqttMessageRow.broker_id == broker_id)
            .order_by(MqttMessageRow.received_at, MqttMessageRow.topic)
        )
        if topics is not None:
            statement = statement.where(MqttMessageRow.topic.in_(tuple(topics)))
        with self._db.session() as session:
            entries = tuple(
                ObservationDeletionEntry(
                    broker_id=row.broker_id,
                    topic=row.topic,
                    observation_id=row.observation_id,
                    received_at=row.received_at,
                    stored_payload_bytes=len(row.payload),
                )
                for row in session.scalars(statement).all()
            )
        return ObservationDeletionPreview(broker_id, entries)

    def delete_previewed(self, preview: ObservationDeletionPreview) -> int:
        """Delete only observations that still match an explicit preview."""
        self.flush()
        if any(entry.broker_id != preview.broker_id for entry in preview.entries):
            raise ValueError("Deletion preview entries must belong to its broker.")
        deleted = 0
        with self._db.transaction() as session:
            for entry in preview.entries:
                result = session.execute(
                    delete(MqttMessageRow).where(
                        MqttMessageRow.broker_id == entry.broker_id,
                        MqttMessageRow.topic == entry.topic,
                        MqttMessageRow.observation_id == entry.observation_id,
                    )
                )
                deleted += result.rowcount or 0
        return deleted

    def enforce_retention(self) -> None:
        """Apply the current automatic retention policy immediately."""
        self.flush()
        if self._policy_provider is not None:
            self._enforce_retention(self._policy_provider())

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
        self._closed = True
        try:
            self.flush()
        finally:
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
            if item is None:
                self._write_queue.task_done()
                return
            batch = [item]
            stop_after_batch = False
            try:
                while len(batch) < self._MAX_WRITE_BATCH:
                    try:
                        queued = self._write_queue.get_nowait()
                    except Empty:
                        break
                    if queued is None:
                        self._write_queue.task_done()
                        stop_after_batch = True
                        break
                    batch.append(queued)

                latest_writes = {
                    (message.broker_id, message.topic): (operation, message)
                    for operation, message in batch
                }
                with self._db.session() as session:
                    policy = (
                        self._policy_provider()
                        if self._policy_provider is not None
                        else None
                    )
                    for operation, message in latest_writes.values():
                        if policy is not None:
                            message = (
                                ObservationRetentionProcessor
                                .truncate_topic_message(message, policy)
                            )
                        row = TopicMessageMapper.to_row(message)
                        if operation == "create":
                            session.add(row)
                        else:
                            session.merge(row)
                    if policy is not None:
                        self._enforce_retention_in_session(session, policy)
                    session.commit()
            except BaseException as error:
                # Check the failure on the caller's next consistency barrier.
                with self._error_lock:
                    if self._write_error is None:
                        self._write_error = error
            finally:
                for _ in batch:
                    self._write_queue.task_done()
            if stop_after_batch:
                return

    def _enforce_retention(self, policy: ObservationRetentionPolicy) -> None:
        with self._db.transaction() as session:
            self._enforce_retention_in_session(session, policy)

    @classmethod
    def _enforce_retention_in_session(cls, session, policy) -> None:
        if policy.auto_remove_expired and policy.max_age_seconds is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(
                seconds=policy.max_age_seconds
            )
            session.execute(
                delete(MqttMessageRow).where(MqttMessageRow.received_at < cutoff)
            )
        if not policy.auto_remove_excess:
            return

        broker_ids = session.scalars(
            select(MqttMessageRow.broker_id)
            .distinct()
            .order_by(MqttMessageRow.broker_id)
        ).all()
        for broker_id in broker_ids:
            rows = session.scalars(
                select(MqttMessageRow)
                .where(MqttMessageRow.broker_id == broker_id)
                .order_by(MqttMessageRow.received_at, MqttMessageRow.topic)
            ).all()
            cls._evict_oldest(
                session,
                rows,
                policy.max_entries_per_broker,
                policy.max_payload_bytes_per_broker,
            )

        rows = session.scalars(
            select(MqttMessageRow).order_by(
                MqttMessageRow.received_at,
                MqttMessageRow.broker_id,
                MqttMessageRow.topic,
            )
        ).all()
        cls._evict_oldest(
            session,
            rows,
            policy.max_entries_total,
            policy.max_persisted_payload_database_bytes_total,
        )

    @staticmethod
    def _evict_oldest(session, rows, max_entries: int, max_bytes: int) -> None:
        stored_bytes = sum(len(row.payload) for row in rows)
        excess_entries = max(0, len(rows) - max_entries)
        index = 0
        while excess_entries > 0 or stored_bytes > max_bytes:
            row = rows[index]
            index += 1
            stored_bytes -= len(row.payload)
            excess_entries = max(0, excess_entries - 1)
            session.delete(row)
