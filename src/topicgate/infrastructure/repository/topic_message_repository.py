from collections.abc import Callable, Collection
from datetime import datetime, timedelta, timezone
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Literal, Tuple
from uuid import UUID

from sqlalchemy import Select, delete, func, select

from topicgate.core.interfaces.stored_observation_administrator import (
    StoredObservationAdministrator,
)
from topicgate.core.interfaces.stored_observation_reader import StoredObservationReader
from topicgate.core.interfaces.topic_message_recorder import TopicMessageRecorder
from topicgate.core.interfaces.topic_message_store import TopicMessageStore
from topicgate.core.models.message_filter import MessageFilter, OrderType
from topicgate.core.models.observation_cache_administration import (
    BrokerCacheUsage,
    CacheUsageSummary,
    ObservationDeletionResult,
)
from topicgate.core.models.observation_deletion_preview import (
    ObservationDeletionEntry,
    ObservationDeletionPreview,
)
from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)
from topicgate.core.models.topic_message import TopicMessage
from topicgate.core.mqtt_topics import mqtt_filter_matches
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.database.mappers.topic_message_mapper import (
    TopicMessageMapper,
)
from topicgate.infrastructure.database.models.mqtt_message_row import MqttMessageRow
from topicgate.processors.observation_retention_processor import (
    ObservationRetentionProcessor,
)


class TopicMessageRepository(
    TopicMessageStore,
    StoredObservationReader,
    StoredObservationAdministrator,
    TopicMessageRecorder,
):
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
            MqttMessageRow.received_at.desc(),
            MqttMessageRow.topic.asc(),
            MqttMessageRow.broker_id.asc(),
        )
        if topic is not None:
            statement = statement.where(MqttMessageRow.topic == topic)
        with self._db.session() as session:
            row = session.scalar(statement.limit(1))
            if row is None:
                raise KeyError("Unknown topic message: latest message")
            return TopicMessageMapper.to_dto(row)

    def get_messages(self, broker_id: UUID) -> tuple[TopicMessage, ...]:
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

    def get_latest_messages(self, broker_id: UUID) -> tuple[TopicMessage, ...]:
        """Return the latest stored state for each topic owned by a broker."""
        return self.get_messages(broker_id)

    def search_message(self, message_filter: MessageFilter) -> tuple[TopicMessage, ...]:
        if message_filter.limit < 0:
            raise ValueError("Message filter limit cannot be negative.")
        self.flush()
        statement = select(MqttMessageRow).where(
            MqttMessageRow.broker_id == message_filter.broker_id
        )

        if message_filter.after is not None:
            statement = statement.where(
                MqttMessageRow.received_at >= message_filter.after
            )
        if message_filter.before is not None:
            statement = statement.where(
                MqttMessageRow.received_at <= message_filter.before
            )

        statement = self._resolve_filter_order(statement, message_filter)

        with self._db.session() as session:
            rows = session.scalars(statement).all()

        # Check MQTT wildcard semantics after SQL has applied its predicates.
        matching_rows = (
            row
            for row in rows
            if mqtt_filter_matches(message_filter.topic_filter, row.topic)
        )
        return tuple(
            TopicMessageMapper.to_dto(row)
            for row in list(matching_rows)[: message_filter.limit]
        )

    def record_message(self, entry: TopicMessage) -> None:
        self.update_message(entry)

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

    def preview_all_deletion(self) -> ObservationDeletionPreview:
        """Describe every persisted observation across all brokers."""
        self.flush()
        statement = select(MqttMessageRow).order_by(
            MqttMessageRow.received_at,
            MqttMessageRow.broker_id,
            MqttMessageRow.topic,
        )
        with self._db.session() as session:
            entries = tuple(
                self._deletion_entry(row) for row in session.scalars(statement).all()
            )
        return ObservationDeletionPreview(None, entries, "all_brokers")

    def cache_usage(self) -> CacheUsageSummary:
        """Return a consistent aggregate after draining pending writes."""
        self.flush()
        statement = (
            select(
                MqttMessageRow.broker_id,
                func.count(MqttMessageRow.topic),
                func.coalesce(func.sum(func.length(MqttMessageRow.payload)), 0),
                func.min(MqttMessageRow.received_at),
                func.max(MqttMessageRow.received_at),
            )
            .group_by(MqttMessageRow.broker_id)
            .order_by(MqttMessageRow.broker_id)
        )
        with self._db.session() as session:
            rows = session.execute(statement).all()
        return CacheUsageSummary(
            tuple(
                BrokerCacheUsage(
                    broker_id=row[0],
                    entry_count=int(row[1]),
                    stored_payload_bytes=int(row[2]),
                    oldest_received_at=row[3],
                    newest_received_at=row[4],
                )
                for row in rows
            )
        )

    def delete_previewed(self, preview: ObservationDeletionPreview) -> int:
        """Delete only observations that still match an explicit preview."""
        return self.delete_previewed_detailed(preview).deleted_count

    def delete_previewed_detailed(
        self,
        preview: ObservationDeletionPreview,
    ) -> ObservationDeletionResult:
        """Delete exact unchanged IDs and report concurrently replaced rows."""
        self.flush()
        if preview.broker_id is not None and any(
            entry.broker_id != preview.broker_id for entry in preview.entries
        ):
            raise ValueError("Deletion preview entries must belong to its broker.")
        deleted: list[ObservationDeletionEntry] = []
        skipped: list[ObservationDeletionEntry] = []
        with self._db.transaction() as session:
            for entry in preview.entries:
                result = session.execute(
                    delete(MqttMessageRow).where(
                        MqttMessageRow.broker_id == entry.broker_id,
                        MqttMessageRow.topic == entry.topic,
                        MqttMessageRow.observation_id == entry.observation_id,
                    )
                )
                if result.rowcount:
                    deleted.append(entry)
                else:
                    skipped.append(entry)
        return ObservationDeletionResult(
            preview.entries,
            tuple(deleted),
            tuple(skipped),
        )

    @staticmethod
    def _deletion_entry(row: MqttMessageRow) -> ObservationDeletionEntry:
        return ObservationDeletionEntry(
            broker_id=row.broker_id,
            topic=row.topic,
            observation_id=row.observation_id,
            received_at=row.received_at,
            stored_payload_bytes=len(row.payload),
        )

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
                                ObservationRetentionProcessor.truncate_topic_message(
                                    message, policy
                                )
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

    @staticmethod
    def _resolve_filter_order(
        statement: Select[Tuple[MqttMessageRow]],
        message_filter: MessageFilter,
    ) -> Select[Tuple[MqttMessageRow]]:
        order = message_filter.order

        match order:
            case OrderType.RECEIVED_ASC:
                return statement.order_by(
                    MqttMessageRow.received_at.asc(),
                    MqttMessageRow.topic.asc(),
                )
            case OrderType.RECEIVED_DESC:
                return statement.order_by(
                    MqttMessageRow.received_at.desc(),
                    MqttMessageRow.topic.asc(),
                )
            case OrderType.TOPIC_ASC:
                return statement.order_by(MqttMessageRow.topic.asc())
            case OrderType.TOPIC_DESC:
                return statement.order_by(MqttMessageRow.topic.desc())
            case OrderType.MESSAGE_COUNT_ASC:
                return statement.order_by(
                    MqttMessageRow.message_count.asc(),
                    MqttMessageRow.topic.asc(),
                )
            case OrderType.MESSAGE_COUNT_DESC:
                return statement.order_by(
                    MqttMessageRow.message_count.desc(),
                    MqttMessageRow.topic.asc(),
                )
            case OrderType.PAYLOAD_SIZE_ASC:
                return statement.order_by(
                    MqttMessageRow.payload_size.asc(),
                    MqttMessageRow.topic.asc(),
                )
            case OrderType.PAYLOAD_SIZE_DESC:
                return statement.order_by(
                    MqttMessageRow.payload_size.desc(),
                    MqttMessageRow.topic.asc(),
                )
            case _:
                raise ValueError(f"Unsupported message order: {order!r}")
