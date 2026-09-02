from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from topicgate.core.models.health import ExpectationFailure, HealthSeverity
from topicgate.core.models.health.health_transition import HealthTransition


@dataclass(frozen=True)
class HealthActionContext:
    expectation_id: UUID
    expectation_revision: int
    transition: HealthTransition
    severity: HealthSeverity
    evaluated_at: datetime
    failure: ExpectationFailure | None
