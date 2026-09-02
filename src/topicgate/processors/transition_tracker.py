from datetime import datetime
from uuid import uuid4

from topicgate.core.models.health import ExpectationState
from topicgate.core.models.health import HealthExpectation
from topicgate.core.models.health import HealthStatus
from topicgate.core.models.health import HealthTransition


class TransitionTracker:
    def apply(
        self,
        expectation: HealthExpectation,
        previous_state: ExpectationState | None,
        status: HealthStatus,
        evaluated_at: datetime,
    ) -> tuple[ExpectationState, HealthTransition | None]:
        previous_status = (
            HealthStatus.UNKNOWN
            if previous_state is None
            else previous_state.current_status
        )
        active_failure_id = (
            None if previous_state is None else previous_state.active_failure_id
        )
        last_healthy_at = (
            None if previous_state is None else previous_state.last_healthy_at
        )
        transition: HealthTransition | None = None

        if status is HealthStatus.HEALTHY:
            last_healthy_at = evaluated_at
            if previous_status is HealthStatus.PROBLEM:
                transition = HealthTransition.RECOVERY
                active_failure_id = None
        elif status is HealthStatus.PROBLEM:
            if active_failure_id is not None:
                transition = HealthTransition.ONGOING_FAILURE
            else:
                transition = HealthTransition.NEW_FAILURE
                active_failure_id = uuid4()

        return (
            ExpectationState(
                expectation_id=expectation.expectation_id,
                current_status=status,
                last_evaluated_at=evaluated_at,
                last_healthy_at=last_healthy_at,
                active_failure_id=active_failure_id,
            ),
            transition,
        )
