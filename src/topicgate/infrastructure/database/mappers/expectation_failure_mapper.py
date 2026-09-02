from topicgate.core.models.health.expectation_failure import ExpectationFailure
from topicgate.infrastructure.database.models.expectation_failure_row import (
    ExpectationFailureRow,
)


class ExpectationFailureMapper:
    """Convert persisted expectation failures to and from domain models."""

    @staticmethod
    def to_row(failure: ExpectationFailure) -> ExpectationFailureRow:
        return ExpectationFailureRow(
            failure_id=failure.failure_id,
            expectation_id=failure.expectation_id,
            first_failed_at=failure.first_failed_at,
            last_seen_at=failure.last_seen_at,
            occurrence_count=failure.occurrence_count,
            expected_revision=failure.expected_revision,
            last_healthy_at=failure.last_healthy_at,
            recovered_at=failure.recovered_at,
            failure_code=failure.failure_code,
            evidence_summary=failure.evidence_summary,
        )

    @staticmethod
    def to_model(row: ExpectationFailureRow) -> ExpectationFailure:
        return ExpectationFailure(
            failure_id=row.failure_id,
            expectation_id=row.expectation_id,
            first_failed_at=row.first_failed_at,
            last_seen_at=row.last_seen_at,
            occurrence_count=row.occurrence_count,
            expected_revision=row.expected_revision,
            last_healthy_at=row.last_healthy_at,
            recovered_at=row.recovered_at,
            failure_code=row.failure_code,
            evidence_summary=row.evidence_summary,
        )
