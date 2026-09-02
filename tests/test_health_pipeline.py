from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from topicgate.app.services.health_expectation_service import (
    HealthExpectationService,
)
from topicgate.core.models.health import ActionKind
from topicgate.core.models.health import Condition
from topicgate.core.models.health import EqualCondition
from topicgate.core.models.health import ExpectationState
from topicgate.core.models.health import HealthExpectation
from topicgate.core.models.health import HealthSeverity
from topicgate.core.models.health import HealthStatus
from topicgate.core.models.health import HealthTransition
from topicgate.core.models.health import TopicTarget
from topicgate.core.models.topic_message import TopicMessage
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.database.models import ExpectationFailureRow
from topicgate.infrastructure.repository.expectation_failure_repository import (
    ExpectationFailureRepository,
)
from topicgate.infrastructure.repository.expectation_state_repository import (
    ExpectationStateRepository,
)
from topicgate.infrastructure.repository.health_expectation_repository import (
    HealthExpectationRepository,
)
from topicgate.processors.action_dispatcher import ActionDispatcher
from topicgate.processors.health_action_registry import HealthActionRegistry
from topicgate.processors.transition_tracker import TransitionTracker


NOW = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)


class FailingCondition(Condition):
    def handle_condition(self, actual: bytes | str) -> HealthStatus:
        raise ValueError("invalid observation")


class StaticExpectationReader:
    def __init__(self, expectations) -> None:
        self._expectations = expectations

    def list_for_topic(self, broker_id, topic):
        return self._expectations


def expectation(broker_id, *, enabled=True, actions=frozenset()):
    return HealthExpectation(
        expectation_id=uuid4(),
        revision=2,
        enabled=enabled,
        severity=HealthSeverity.CRITICAL,
        target=TopicTarget(broker_id, "devices/status"),
        condition=EqualCondition(b"online"),
        actions=actions,
    )


def message(broker_id, payload=b"offline", *, received_at=NOW):
    return TopicMessage(
        broker_id=broker_id,
        topic="devices/status",
        payload=payload,
        qos=0,
        retain=False,
        received_at=received_at,
        payload_size=len(payload),
        message_count=1,
        observation_id=uuid4(),
    )


def service(database, actions=None):
    expectations = HealthExpectationRepository(database)
    states = ExpectationStateRepository(database)
    failures = ExpectationFailureRepository(database)
    dispatcher = ActionDispatcher(HealthActionRegistry(actions or {}))
    return (
        HealthExpectationService(
            expectations,
            states,
            failures,
            database,
            TransitionTracker(),
            dispatcher,
        ),
        expectations,
        states,
        failures,
    )


@pytest.mark.parametrize(
    ("previous_status", "status", "transition", "retains_failure"),
    [
        (None, HealthStatus.HEALTHY, None, False),
        (None, HealthStatus.PROBLEM, HealthTransition.NEW_FAILURE, True),
        (
            HealthStatus.UNKNOWN,
            HealthStatus.PROBLEM,
            HealthTransition.NEW_FAILURE,
            True,
        ),
        (
            HealthStatus.HEALTHY,
            HealthStatus.PROBLEM,
            HealthTransition.NEW_FAILURE,
            True,
        ),
        (
            HealthStatus.PROBLEM,
            HealthStatus.PROBLEM,
            HealthTransition.ONGOING_FAILURE,
            True,
        ),
        (HealthStatus.PROBLEM, HealthStatus.HEALTHY, HealthTransition.RECOVERY, False),
        (HealthStatus.PROBLEM, HealthStatus.UNKNOWN, None, True),
    ],
)
def test_transition_tracker_matrix(
    previous_status,
    status,
    transition,
    retains_failure,
) -> None:
    broker_id = uuid4()
    item = expectation(broker_id)
    failure_id = uuid4()
    previous = (
        None
        if previous_status is None
        else ExpectationState(
            item.expectation_id,
            previous_status,
            last_healthy_at=NOW - timedelta(minutes=1),
            active_failure_id=(
                failure_id if previous_status is HealthStatus.PROBLEM else None
            ),
        )
    )

    state, actual_transition = TransitionTracker().apply(
        item,
        previous,
        status,
        NOW,
    )

    assert actual_transition is transition
    assert state.current_status is status
    assert state.last_evaluated_at == NOW
    assert (state.active_failure_id is not None) is retains_failure
    if previous_status is HealthStatus.PROBLEM and retains_failure:
        assert state.active_failure_id == failure_id


def test_unknown_observation_retains_and_resumes_unresolved_failure() -> None:
    broker_id = uuid4()
    item = expectation(broker_id)
    failure_id = uuid4()
    unknown_state = ExpectationState(
        item.expectation_id,
        HealthStatus.UNKNOWN,
        active_failure_id=failure_id,
    )

    state, transition = TransitionTracker().apply(
        item,
        unknown_state,
        HealthStatus.PROBLEM,
        NOW,
    )

    assert transition is HealthTransition.ONGOING_FAILURE
    assert state.active_failure_id == failure_id


def test_pipeline_creates_repeats_and_recovers_one_failure_episode(tmp_path) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'pipeline.db'}")
    handler = MagicMock()
    pipeline, expectations, states, failures = service(
        database,
        {ActionKind.LOG: handler},
    )
    broker_id = uuid4()
    item = expectation(broker_id, actions=frozenset({ActionKind.LOG}))
    expectations.create(item)

    pipeline.evaluate_observation(message(broker_id))
    failed_state = states.get(item.expectation_id)
    assert failed_state is not None
    assert failed_state.active_failure_id is not None
    failure_id = failed_state.active_failure_id
    failure = failures.get(failure_id)
    assert failure is not None
    assert failure.occurrence_count == 1
    assert handler.execute.call_count == 1
    first_context = handler.execute.call_args.args[0]
    assert first_context.transition is HealthTransition.NEW_FAILURE
    assert first_context.severity is HealthSeverity.CRITICAL

    pipeline.evaluate_observation(
        message(broker_id, received_at=NOW + timedelta(minutes=1))
    )
    assert failures.get(failure_id).occurrence_count == 2
    assert handler.execute.call_count == 1

    pipeline.evaluate_observation(
        message(
            broker_id,
            b"online",
            received_at=NOW + timedelta(minutes=2),
        )
    )
    recovered_state = states.get(item.expectation_id)
    recovered = failures.get(failure_id)
    assert recovered_state.current_status is HealthStatus.HEALTHY
    assert recovered_state.active_failure_id is None
    assert recovered.recovered_at is not None
    assert handler.execute.call_count == 2
    assert handler.execute.call_args.args[0].transition is HealthTransition.RECOVERY
    database.dispose()


def test_pipeline_no_expectations_and_disabled_expectations_are_safe_noops(
    tmp_path,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'noop.db'}")
    pipeline, expectations, states, _ = service(database)
    broker_id = uuid4()

    pipeline.evaluate_observation(message(broker_id))
    disabled = expectation(broker_id, enabled=False)
    expectations.create(disabled)
    pipeline.evaluate_observation(message(broker_id))

    assert states.get(disabled.expectation_id) is None
    database.dispose()


def test_evaluator_failure_does_not_block_other_expectations(tmp_path) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'evaluation.db'}")
    _, expectations, states, failures = service(database)
    broker_id = uuid4()
    broken_row = expectation(broker_id)
    healthy = expectation(broker_id)
    expectations.create(broken_row)
    expectations.create(healthy)
    reader = StaticExpectationReader(
        (replace(broken_row, condition=FailingCondition()), healthy)
    )
    pipeline = HealthExpectationService(
        reader,
        states,
        failures,
        database,
        TransitionTracker(),
        ActionDispatcher(HealthActionRegistry({})),
    )

    pipeline.evaluate_observation(message(broker_id))

    assert states.get(broken_row.expectation_id) is None
    assert states.get(healthy.expectation_id).current_status is HealthStatus.PROBLEM
    database.dispose()


def test_pipeline_isolates_missing_and_failing_action_handlers(
    tmp_path,
    caplog,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'actions.db'}")
    failing = MagicMock()
    failing.execute.side_effect = RuntimeError("handler failed")
    pipeline, expectations, states, _ = service(
        database,
        {ActionKind.LOG: failing},
    )
    broker_id = uuid4()
    item = expectation(
        broker_id,
        actions=frozenset({ActionKind.LOG, ActionKind.STORE_FAILURE}),
    )
    expectations.create(item)

    pipeline.evaluate_observation(message(broker_id))

    assert states.get(item.expectation_id).current_status is HealthStatus.PROBLEM
    assert "No health action handler is registered for store_failure" in caplog.text
    assert "Health action log failed" in caplog.text
    database.dispose()


def test_pipeline_rolls_back_failure_when_state_write_fails(tmp_path) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'rollback.db'}")
    pipeline, expectations, states, failures = service(database)
    broker_id = uuid4()
    item = expectation(broker_id)
    expectations.create(item)
    original_upsert = states.upsert
    states.upsert = MagicMock(side_effect=RuntimeError("state write failed"))

    pipeline.evaluate_observation(message(broker_id))

    states.upsert = original_upsert
    assert states.get(item.expectation_id) is None
    with database.session() as session:
        failure_count = session.scalar(
            select(func.count()).select_from(ExpectationFailureRow)
        )
        assert failure_count == 0
    database.dispose()
