from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)
from topicgate.infrastructure.database.models.observation_retention_policy_row import (
    ObservationRetentionPolicyRow,
)


class ObservationRetentionPolicyMapper:
    """Map the persisted singleton retention policy to its domain model."""

    @staticmethod
    def to_row(policy: ObservationRetentionPolicy) -> ObservationRetentionPolicyRow:
        row = ObservationRetentionPolicyRow(id=1)
        ObservationRetentionPolicyMapper.apply(policy, row)
        return row

    @staticmethod
    def apply(
        policy: ObservationRetentionPolicy,
        row: ObservationRetentionPolicyRow,
    ) -> None:
        row.max_entries_per_broker = policy.max_entries_per_broker
        row.max_entries_total = policy.max_entries_total
        row.warning_threshold = policy.warning_threshold
        row.max_payload_bytes_per_topic = policy.max_payload_bytes_per_topic
        row.max_payload_bytes_per_broker = policy.max_payload_bytes_per_broker
        row.max_persisted_payload_database_bytes_total = (
            policy.max_persisted_payload_database_bytes_total
        )
        row.max_age_seconds = policy.max_age_seconds
        row.auto_remove_expired = policy.auto_remove_expired
        row.auto_remove_excess = policy.auto_remove_excess
        row.auto_remove_unsubscribed = policy.auto_remove_unsubscribed

    @staticmethod
    def to_policy(
        row: ObservationRetentionPolicyRow,
    ) -> ObservationRetentionPolicy:
        return ObservationRetentionPolicy(
            max_entries_per_broker=row.max_entries_per_broker,
            max_entries_total=row.max_entries_total,
            warning_threshold=row.warning_threshold,
            max_payload_bytes_per_topic=row.max_payload_bytes_per_topic,
            max_payload_bytes_per_broker=row.max_payload_bytes_per_broker,
            max_persisted_payload_database_bytes_total=(
                row.max_persisted_payload_database_bytes_total
            ),
            max_age_seconds=row.max_age_seconds,
            auto_remove_expired=row.auto_remove_expired,
            auto_remove_excess=row.auto_remove_excess,
            auto_remove_unsubscribed=row.auto_remove_unsubscribed,
        )
