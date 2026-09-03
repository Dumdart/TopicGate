import base64
from typing import Any
from uuid import UUID

from topicgate.core.models.health.condition import Condition
from topicgate.core.models.health.condition import EqualCondition
from topicgate.core.models.health.expectation_target import BrokerTarget
from topicgate.core.models.health.expectation_target import ExpectationTarget
from topicgate.core.models.health.expectation_target import TopicTarget
from topicgate.core.models.health.health_enums import ActionKind
from topicgate.core.models.health.health_enums import HealthSeverity
from topicgate.core.models.health.health_expectation import HealthExpectation
from topicgate.infrastructure.database.models.health_expectation_row import (
    HealthExpectationRow,
)


class HealthExpectationMapper:
    """Convert health expectations and their JSON fields to and from rows."""

    @staticmethod
    def to_row(expectation: HealthExpectation) -> HealthExpectationRow:
        return HealthExpectationRow(
            expectation_id=expectation.expectation_id,
            revision=expectation.revision,
            enabled=expectation.enabled,
            severity=expectation.severity.value,
            target=HealthExpectationMapper._target_to_dict(expectation.target),
            condition=HealthExpectationMapper._condition_to_dict(
                expectation.condition
            ),
            actions=sorted(action.value for action in expectation.actions),
            name=expectation.name,
            description=expectation.description,
        )

    @staticmethod
    def to_model(row: HealthExpectationRow) -> HealthExpectation:
        return HealthExpectation(
            expectation_id=row.expectation_id,
            revision=row.revision,
            enabled=row.enabled,
            severity=HealthSeverity(row.severity),
            target=HealthExpectationMapper._dict_to_target(row.target),
            condition=HealthExpectationMapper._dict_to_condition(row.condition),
            actions=frozenset(ActionKind(action) for action in row.actions),
            name=getattr(row, "name", "") or "",
            description=getattr(row, "description", "") or "",
        )

    @staticmethod
    def _target_to_dict(target: ExpectationTarget) -> dict[str, str]:
        if isinstance(target, BrokerTarget):
            return {"kind": "broker", "broker_id": str(target.broker_id)}
        if isinstance(target, TopicTarget):
            return {
                "kind": "topic",
                "broker_id": str(target.broker_id),
                "topic": target.topic,
            }
        raise ValueError(f"Unsupported expectation target: {type(target).__name__}")

    @staticmethod
    def _dict_to_target(value: dict[str, Any]) -> ExpectationTarget:
        kind = value.get("kind")
        broker_id = HealthExpectationMapper._required_uuid(value, "broker_id")
        if kind == "broker":
            return BrokerTarget(broker_id=broker_id)
        if kind == "topic":
            topic = value.get("topic")
            if not isinstance(topic, str):
                raise ValueError("Expectation topic must be a string.")
            return TopicTarget(broker_id=broker_id, topic=topic)
        raise ValueError(f"Unsupported expectation target kind: {kind!r}")

    @staticmethod
    def _condition_to_dict(condition: Condition) -> dict[str, Any]:
        if not isinstance(condition, EqualCondition):
            raise ValueError(
                f"Unsupported expectation condition: {type(condition).__name__}"
            )
        if isinstance(condition.expected_value, bytes):
            return {
                "kind": "equal",
                "expected_value": base64.b64encode(
                    condition.expected_value
                ).decode("ascii"),
                "value_type": "bytes",
            }
        if isinstance(condition.expected_value, str):
            return {"kind": "equal", "expected_value": condition.expected_value}
        raise ValueError("Equal condition expected value must be bytes or a string.")

    @staticmethod
    def _dict_to_condition(value: dict[str, Any]) -> Condition:
        if value.get("kind") != "equal":
            raise ValueError(
                "Unsupported expectation condition kind: "
                f"{value.get('kind')!r}"
            )
        expected_value = value.get("expected_value")
        if value.get("value_type") == "bytes":
            if not isinstance(expected_value, str):
                raise ValueError("Encoded bytes condition value must be a string.")
            try:
                expected_value = base64.b64decode(expected_value, validate=True)
            except ValueError as error:
                raise ValueError(
                    "Encoded bytes condition value is invalid."
                ) from error
        elif not isinstance(expected_value, str):
            raise ValueError("Equal condition expected value must be a string.")
        return EqualCondition(expected_value=expected_value)

    @staticmethod
    def _required_uuid(value: dict[str, Any], field_name: str) -> UUID:
        raw_value = value.get(field_name)
        if not isinstance(raw_value, (str, UUID)):
            raise ValueError(f"Expectation {field_name} must be a UUID.")
        try:
            return raw_value if isinstance(raw_value, UUID) else UUID(raw_value)
        except ValueError as error:
            raise ValueError(f"Expectation {field_name} must be a UUID.") from error
