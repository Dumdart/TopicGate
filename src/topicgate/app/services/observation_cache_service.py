from collections.abc import Collection
from uuid import UUID

from topicgate.core.models.observation_deletion_preview import (
    ObservationDeletionPreview,
)
from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)
from topicgate.core.models.subscription import Subscription
from topicgate.core.mqtt_topics import mqtt_filter_matches
from topicgate.app.services.observation_retention_policy_service import (
    ObservationRetentionPolicyService,
)
from topicgate.infrastructure.repository.topic_message_repository import (
    TopicMessageRepository,
)


class ObservationCacheService:
    """Coordinate retention settings and confirmed cache deletion."""

    def __init__(
        self,
        messages: TopicMessageRepository,
        policies: ObservationRetentionPolicyService,
    ) -> None:
        self._messages = messages
        self._policies = policies

    def get_retention_policy(self) -> ObservationRetentionPolicy:
        return self._policies.get()

    def update_retention_policy(
        self,
        policy: ObservationRetentionPolicy,
    ) -> ObservationRetentionPolicy:
        persisted = self._policies.update(policy)
        self._messages.enforce_retention()
        return persisted

    def preview_clear_cache(
        self,
        broker_id: UUID,
        topics: Collection[str] | None = None,
    ) -> ObservationDeletionPreview:
        return self._messages.preview_deletion(broker_id, topics)

    def preview_unsubscribed(
        self,
        broker_id: UUID,
        subscriptions: Collection[Subscription],
    ) -> ObservationDeletionPreview:
        preview = self._messages.preview_deletion(broker_id)
        entries = tuple(
            entry
            for entry in preview.entries
            if not any(
                mqtt_filter_matches(subscription.topic_filter, entry.topic)
                for subscription in subscriptions
            )
        )
        return ObservationDeletionPreview(broker_id, entries)

    def confirm_deletion(self, preview: ObservationDeletionPreview) -> int:
        return self._messages.delete_previewed(preview)

    def flush_pending_writes(self) -> None:
        self._messages.flush()
