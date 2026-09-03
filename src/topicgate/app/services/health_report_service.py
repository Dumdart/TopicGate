from datetime import datetime
from uuid import UUID

from topicgate.core.interfaces.health_repositories import (
    ExpectationFailureStore,
    ExpectationStateStore,
    HealthExpectationReader,
)
from topicgate.core.models.health import (
    BrokerTarget,
    ExpectationFailure,
    ExpectationState,
    TopicTarget,
)


class HealthReportService:
    def __init__(
        self,
        health_expectation_repository: HealthExpectationReader,
        expectation_state_repository: ExpectationStateStore,
        expectation_failure_repository: ExpectationFailureStore,
    ) -> None:
        self._health_expectation_repository = health_expectation_repository
        self._expectation_state_repository = expectation_state_repository
        self._expectation_failure_repository = expectation_failure_repository

    def get_expectation_states(self) -> list[ExpectationState]:
        return self._expectation_state_repository.get_all_states()

    def get_last_evaluated(self) -> datetime | None:
        return _latest(
            state.last_evaluated_at for state in self.get_expectation_states()
        )

    def get_last_healthy(self) -> datetime | None:
        return _latest(
            state.last_healthy_at for state in self.get_expectation_states()
        )

    def get_active_failures(self) -> list[ExpectationFailure]:
        return [
            failure
            for failure in self._expectation_failure_repository.get_all_states()
            if failure.recovered_at is None
        ]

    def broker_identity(self, failure: ExpectationFailure) -> UUID:
        target = self._get_expectation(failure).target
        if not isinstance(target, (BrokerTarget, TopicTarget)):
            raise TypeError(f"Unsupported expectation target: {type(target).__name__}")
        return target.broker_id

    def target_identity(self, failure: ExpectationFailure) -> str:
        target = self._get_expectation(failure).target
        if isinstance(target, TopicTarget):
            return target.topic
        if isinstance(target, BrokerTarget):
            return "broker"
        raise TypeError(f"Unsupported expectation target: {type(target).__name__}")

    def get_evidence_limitations(
        self, failure: ExpectationFailure
    ) -> tuple[str, ...]:
        if failure.evidence_summary is None:
            return ("evidence_unavailable",)
        return ()

    def _get_expectation(self, failure: ExpectationFailure):
        expectation = self._health_expectation_repository.get(
            failure.expectation_id
        )
        if expectation is None:
            raise KeyError(f"Unknown health expectation: {failure.expectation_id}")
        return expectation


def _latest(values) -> datetime | None:
    timestamps = [value for value in values if value is not None]
    return max(timestamps) if timestamps else None
