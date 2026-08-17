from dataclasses import replace
from unittest.mock import MagicMock

from topicgate.app.services.observation_retention_policy_service import (
    ObservationRetentionPolicyService,
)
from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)


def test_policy_service_caches_reads_and_refreshes_after_update() -> None:
    repository = MagicMock()
    initial = ObservationRetentionPolicy()
    updated = replace(initial, max_entries_per_broker=500)
    repository.get.return_value = initial
    repository.update.return_value = updated
    service = ObservationRetentionPolicyService(repository)

    assert service.get() is initial
    assert service.get() is initial
    assert service.update(updated) is updated
    assert service.get() is updated
    repository.get.assert_called_once_with()
    repository.update.assert_called_once_with(updated)
