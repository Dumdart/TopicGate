from abc import ABC, abstractmethod
from dataclasses import dataclass

from topicgate.core.models.health.health_enums import HealthStatus


class Condition(ABC):
    @abstractmethod
    def handle_condition(self, actual: bytes | str) -> HealthStatus:
        """Evaluate an observed value and return its health status."""


@dataclass(frozen=True)
class EqualCondition(Condition):
    expected_value: bytes | str

    @staticmethod
    def compare(actual: bytes | str, expected: bytes | str) -> bool:
        if type(actual) is not type(expected):
            raise TypeError("Actual and expected values must have the same type.")
        return actual == expected

    def handle_condition(self, actual: bytes | str) -> HealthStatus:
        return (
            HealthStatus.HEALTHY
            if self.compare(actual, self.expected_value)
            else HealthStatus.PROBLEM
        )
