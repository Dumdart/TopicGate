from dataclasses import replace

import pytest
from sqlalchemy import delete

from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.database.models.observation_retention_policy_row import (
    ObservationRetentionPolicyRow,
)
from topicgate.infrastructure.repository.observation_retention_policy_repository import (
    ObservationRetentionPolicyRepository,
)


def test_repository_reads_seeded_defaults_and_persists_updates() -> None:
    database = DatabaseContext("sqlite:///:memory:")
    repository = ObservationRetentionPolicyRepository(database)
    expected = replace(
        ObservationRetentionPolicy(),
        max_entries_per_broker=2_000,
        max_entries_total=20_000,
        max_age_seconds=31_536_000,
        auto_remove_unsubscribed=True,
    )

    assert repository.get() == ObservationRetentionPolicy()
    assert repository.update(expected) == expected
    assert repository.get() == expected
    database.dispose()


def test_repository_treats_a_missing_singleton_as_corruption() -> None:
    database = DatabaseContext("sqlite:///:memory:")
    repository = ObservationRetentionPolicyRepository(database)
    with database.transaction() as session:
        session.execute(delete(ObservationRetentionPolicyRow))

    try:
        with pytest.raises(RuntimeError, match="retention policy is missing"):
            repository.get()
        with pytest.raises(RuntimeError, match="retention policy is missing"):
            repository.update(ObservationRetentionPolicy())
    finally:
        database.dispose()
