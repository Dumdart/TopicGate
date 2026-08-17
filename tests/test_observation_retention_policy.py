from dataclasses import replace

import pytest

from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)
from topicgate.infrastructure.database.mappers.observation_retention_policy_mapper import (
    ObservationRetentionPolicyMapper,
)


def test_observation_retention_policy_has_safe_defaults() -> None:
    policy = ObservationRetentionPolicy()

    assert policy.max_entries_per_broker == 1_000
    assert policy.max_entries_total == 10_000
    assert policy.warning_threshold == 0.80
    assert policy.max_payload_bytes_per_topic == 64 * 1024
    assert policy.max_payload_bytes_per_broker == 8 * 1024 * 1024
    assert (
        policy.max_persisted_payload_database_bytes_total
        == 256 * 1024 * 1024
    )
    assert policy.max_age_seconds is None
    assert policy.auto_remove_expired is True
    assert policy.auto_remove_excess is True
    assert policy.auto_remove_unsubscribed is False


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"max_entries_per_broker": 0}, "positive integer"),
        ({"warning_threshold": 0}, "greater than 0"),
        ({"warning_threshold": 1.1}, "at most 1"),
        ({"max_age_seconds": 0}, "positive integer or None"),
        (
            {"max_entries_per_broker": 10_001},
            "cannot exceed max_entries_total",
        ),
        (
            {"max_payload_bytes_per_topic": 9 * 1024 * 1024},
            "cannot exceed max_payload_bytes_per_broker",
        ),
        ({"auto_remove_expired": 1}, "must be a boolean"),
    ],
)
def test_observation_retention_policy_rejects_invalid_limits(
    changes,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        replace(ObservationRetentionPolicy(), **changes)


def test_observation_retention_policy_mapper_round_trips_custom_values() -> None:
    policy = ObservationRetentionPolicy(
        max_entries_per_broker=2_000,
        max_entries_total=20_000,
        warning_threshold=0.75,
        max_payload_bytes_per_topic=128 * 1024,
        max_payload_bytes_per_broker=16 * 1024 * 1024,
        max_persisted_payload_database_bytes_total=512 * 1024 * 1024,
        max_age_seconds=86_400,
        auto_remove_expired=False,
        auto_remove_excess=True,
        auto_remove_unsubscribed=True,
    )

    row = ObservationRetentionPolicyMapper.to_row(policy)

    assert row.id == 1
    assert ObservationRetentionPolicyMapper.to_policy(row) == policy


def test_observation_retention_policy_mapper_preserves_unlimited_age() -> None:
    policy = ObservationRetentionPolicy(max_age_seconds=None)

    assert (
        ObservationRetentionPolicyMapper.to_policy(
            ObservationRetentionPolicyMapper.to_row(policy)
        ).max_age_seconds
        is None
    )
