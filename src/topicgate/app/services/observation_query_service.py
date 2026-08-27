from collections.abc import Collection
from uuid import UUID

from topicgate.core.interfaces.stored_observation_reader import StoredObservationReader
from topicgate.core.models.message_filter import MessageFilter
from topicgate.core.models.observation_cache_administration import (
    CacheUsageSummary,
    PersistedTopicSummary,
)
from topicgate.core.models.subscription import Subscription
from topicgate.core.models.topic_message import TopicMessage
from topicgate.core.mqtt_topics import mqtt_filter_matches


class ObservationQueryService:
    def __init__(self, stored_reader: StoredObservationReader) -> None:
        self._stored_reader = stored_reader

    def get_message(self, message_id: UUID) -> TopicMessage:
        return self._stored_reader.get_message(message_id)

    def get_broker_messages(self, broker_id: UUID) -> tuple[TopicMessage, ...]:
        return self._stored_reader.get_messages(broker_id)

    def get_latest_message(self, topic: str | None = None) -> TopicMessage:
        return self._stored_reader.get_latest_message(topic)

    def query_stored_observations(
        self, message_filter: MessageFilter
    ) -> tuple[TopicMessage, ...]:
        return self._stored_reader.search_message(message_filter)

    def get_cache_usage(self) -> CacheUsageSummary:
        return self._stored_reader.cache_usage()

    def get_persisted_topics(
        self,
        broker_id: UUID,
        subscriptions: Collection[Subscription],
    ) -> tuple[PersistedTopicSummary, ...]:
        preview = self._stored_reader.preview_deletion(broker_id)
        return tuple(
            PersistedTopicSummary(
                broker_id=entry.broker_id,
                topic=entry.topic,
                observation_id=entry.observation_id,
                stored_payload_bytes=entry.stored_payload_bytes,
                received_at=entry.received_at,
                is_subscribed=any(
                    mqtt_filter_matches(item.topic_filter, entry.topic)
                    for item in subscriptions
                ),
            )
            for entry in preview.entries
        )
