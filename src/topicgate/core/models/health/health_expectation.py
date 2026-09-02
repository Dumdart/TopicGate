from dataclasses import dataclass
from uuid import UUID

from topicgate.core.models.health.condition import Condition
from topicgate.core.models.health.condition import EqualCondition
from topicgate.core.models.health.expectation_target import BrokerTarget
from topicgate.core.models.health.expectation_target import ExpectationTarget
from topicgate.core.models.health.expectation_target import TopicTarget
from topicgate.core.models.health.health_enums import ActionKind
from topicgate.core.models.health.health_enums import HealthSeverity


@dataclass
class HealthExpectation:
    expectation_id: UUID
    revision: int
    enabled: bool
    severity: HealthSeverity
    target: ExpectationTarget
    condition: Condition
    actions: frozenset[ActionKind]


__all__ = [
    "ActionKind",
    "BrokerTarget",
    "Condition",
    "EqualCondition",
    "ExpectationTarget",
    "HealthExpectation",
    "HealthSeverity",
    "TopicTarget",
]
