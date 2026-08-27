from collections import defaultdict
from collections.abc import Collection, Mapping
from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

from topicgate.app.services.observation_retention_policy_service import (
    ObservationRetentionPolicyService,
)
from topicgate.core.interfaces.stored_observation_administrator import (
    StoredObservationAdministrator,
)
from topicgate.core.interfaces.stored_observation_reader import (
    StoredObservationReader,
)
from topicgate.core.models.observation_cache_administration import (
    ObservationDeletionResult,
    RetentionImpactGroup,
    RetentionPolicyApplicationResult,
    RetentionPolicyPreview,
    RetentionRemovalReason,
)
from topicgate.core.models.observation_deletion_preview import (
    ObservationDeletionEntry,
    ObservationDeletionPreview,
)
from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)
from topicgate.core.models.subscription import Subscription
from topicgate.core.mqtt_topics import mqtt_filter_matches


class ObservationCacheService:
    """Coordinate retention settings and confirmed cache deletion."""

    def __init__(
        self,
        stored_reader: StoredObservationReader,
        policies: ObservationRetentionPolicyService,
        *,
        administrator: StoredObservationAdministrator | None = None,
    ) -> None:
        self._stored_reader = stored_reader
        self._stored_administrator = (
            cast(StoredObservationAdministrator, cast(object, stored_reader))
            if administrator is None
            else administrator
        )
        self._policies = policies

    def get_retention_policy(self) -> ObservationRetentionPolicy:
        return self._policies.get()

    def update_retention_policy(
        self,
        policy: ObservationRetentionPolicy,
    ) -> ObservationRetentionPolicy:
        persisted = self._policies.update(policy)
        self._stored_administrator.enforce_retention()
        return persisted

    def preview_clear_cache(
        self,
        broker_id: UUID,
        topics: Collection[str] | None = None,
    ) -> ObservationDeletionPreview:
        return self._stored_reader.preview_deletion(broker_id, topics)

    def preview_unsubscribed(
        self,
        broker_id: UUID,
        subscriptions: Collection[Subscription],
    ) -> ObservationDeletionPreview:
        preview = self._stored_reader.preview_deletion(broker_id)
        entries = tuple(
            entry
            for entry in preview.entries
            if not any(
                mqtt_filter_matches(subscription.topic_filter, entry.topic)
                for subscription in subscriptions
            )
        )
        return ObservationDeletionPreview(broker_id, entries)

    def preview_all(self) -> ObservationDeletionPreview:
        return self._stored_reader.preview_all_deletion()

    def confirm_deletion_detailed(
        self,
        preview: ObservationDeletionPreview,
    ) -> ObservationDeletionResult:
        return self._stored_administrator.delete_previewed_detailed(preview)

    def preview_retention_policy(
        self,
        policy: ObservationRetentionPolicy,
        subscriptions: Mapping[UUID, Collection[Subscription]],
        *,
        now: datetime | None = None,
    ) -> RetentionPolicyPreview:
        current = self._policies.get()
        all_entries = self._stored_reader.preview_all_deletion().entries
        grouped = self._retention_impact(
            all_entries,
            policy,
            subscriptions,
            now=now or datetime.now(timezone.utc),
        )
        entries = tuple(entry for group in grouped for entry in group.entries)
        return RetentionPolicyPreview(
            current,
            policy,
            ObservationDeletionPreview(None, entries, "policy_enforcement"),
            grouped,
        )

    def confirm_retention_policy(
        self,
        preview: RetentionPolicyPreview,
        subscriptions: Mapping[UUID, Collection[Subscription]],
    ) -> RetentionPolicyApplicationResult:
        if self._policies.get() != preview.previous_policy:
            raise ValueError("The retention policy changed after preview.")
        current = self.preview_retention_policy(
            preview.proposed_policy,
            subscriptions,
        )
        if current.deletion.entries != preview.deletion.entries:
            raise ValueError(
                "Persisted observations changed after preview; preview again."
            )
        enforcement = self.confirm_deletion_detailed(preview.deletion)
        persisted = self._policies.update(preview.proposed_policy)
        return RetentionPolicyApplicationResult(persisted, enforcement)

    def confirm_deletion(self, preview: ObservationDeletionPreview) -> int:
        return self.confirm_deletion_detailed(preview).deleted_count

    def flush_pending_writes(self) -> None:
        self._stored_administrator.flush()

    @classmethod
    def _retention_impact(
        cls,
        entries: tuple[ObservationDeletionEntry, ...],
        policy: ObservationRetentionPolicy,
        subscriptions: Mapping[UUID, Collection[Subscription]],
        *,
        now: datetime,
    ) -> tuple[RetentionImpactGroup, ...]:
        ordered = sorted(
            entries,
            key=lambda item: (
                cls._utc(item.received_at),
                str(item.broker_id),
                item.topic,
                str(item.observation_id),
            ),
        )
        reasons: dict[UUID, RetentionRemovalReason] = {}
        if policy.auto_remove_expired and policy.max_age_seconds is not None:
            cutoff = cls._utc(now) - timedelta(seconds=policy.max_age_seconds)
            for entry in ordered:
                if cls._utc(entry.received_at) < cutoff:
                    reasons[entry.observation_id] = RetentionRemovalReason.EXPIRED

        if policy.auto_remove_unsubscribed:
            for entry in ordered:
                if entry.observation_id in reasons:
                    continue
                if not any(
                    mqtt_filter_matches(item.topic_filter, entry.topic)
                    for item in subscriptions.get(entry.broker_id, ())
                ):
                    reasons[entry.observation_id] = RetentionRemovalReason.UNSUBSCRIBED

        if policy.auto_remove_excess:
            by_broker: dict[UUID, list[ObservationDeletionEntry]] = defaultdict(list)
            for entry in ordered:
                if entry.observation_id not in reasons:
                    by_broker[entry.broker_id].append(entry)
            for broker_entries in by_broker.values():
                stored_bytes = sum(item.stored_payload_bytes for item in broker_entries)
                while (
                    len(broker_entries) > policy.max_entries_per_broker
                    or stored_bytes > policy.max_payload_bytes_per_broker
                ):
                    reason = (
                        RetentionRemovalReason.PER_BROKER_ENTRY_LIMIT
                        if len(broker_entries) > policy.max_entries_per_broker
                        else RetentionRemovalReason.PER_BROKER_BYTE_LIMIT
                    )
                    removed = broker_entries.pop(0)
                    stored_bytes -= removed.stored_payload_bytes
                    reasons[removed.observation_id] = reason

            remaining = [
                entry for entry in ordered if entry.observation_id not in reasons
            ]
            stored_bytes = sum(item.stored_payload_bytes for item in remaining)
            while (
                len(remaining) > policy.max_entries_total
                or stored_bytes > policy.max_persisted_payload_database_bytes_total
            ):
                reason = (
                    RetentionRemovalReason.GLOBAL_ENTRY_LIMIT
                    if len(remaining) > policy.max_entries_total
                    else RetentionRemovalReason.GLOBAL_BYTE_LIMIT
                )
                removed = remaining.pop(0)
                stored_bytes -= removed.stored_payload_bytes
                reasons[removed.observation_id] = reason

        groups: dict[
            tuple[UUID, RetentionRemovalReason],
            list[ObservationDeletionEntry],
        ] = defaultdict(list)
        for entry in ordered:
            reason = reasons.get(entry.observation_id)
            if reason is not None:
                groups[(entry.broker_id, reason)].append(entry)
        return tuple(
            RetentionImpactGroup(broker_id, reason, tuple(items))
            for (broker_id, reason), items in sorted(
                groups.items(), key=lambda item: (str(item[0][0]), item[0][1].value)
            )
        )

    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
