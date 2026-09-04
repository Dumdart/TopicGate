import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from topicgate.app.services.broker_health_monitor import BrokerHealthMonitor
from topicgate.app.services.health_expectation_service import (
    HealthExpectationService,
)
from topicgate.core.models.connection_status import ConnectionStatus
from topicgate.core.models.current_topic import CurrentTopic
from topicgate.core.models.health import BrokerTarget
from topicgate.core.models.health import EqualCondition
from topicgate.core.models.health import HealthExpectation
from topicgate.core.models.health import HealthSeverity
from topicgate.core.models.health import HealthStatus
from topicgate.core.models.health import ObservationFindingCode
from topicgate.core.models.health import TopicTarget
from topicgate.core.models.observation_status import ObservationStatus
from topicgate.core.models.subscription import Subscription
from topicgate.core.models.topic_message import TopicMessage
from topicgate.infrastructure.database.database_context import DatabaseContext
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


NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)


def _expectation(broker_id) -> HealthExpectation:
    return HealthExpectation(
        expectation_id=uuid4(),
        revision=1,
        enabled=True,
        severity=HealthSeverity.CRITICAL,
        target=TopicTarget(broker_id, "devices/status"),
        condition=EqualCondition(b"online"),
        actions=frozenset(),
    )


def _metadata(**overrides):
    values = {
        "connection_status": ConnectionStatus.CONNECTED,
        "observation_started_at": NOW - timedelta(minutes=10),
        "dropped_message_count": 0,
        "recording_failure_count": 0,
        "subscription_failure_count": 0,
        "subscription_rejected_count": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _service(database, item, metadata, current_topics=(), subscriptions=None):
    expectations = HealthExpectationRepository(database)
    expectations.create(item)
    return HealthExpectationService(
        expectations,
        ExpectationStateRepository(database),
        ExpectationFailureRepository(database),
        database,
        TransitionTracker(),
        ActionDispatcher(HealthActionRegistry({})),
        subscriptions_reader=lambda _broker_id: (
            (Subscription("devices/#"),)
            if subscriptions is None
            else subscriptions
        ),
        broker_metadata_reader=lambda _broker_id: metadata,
        current_topics_reader=lambda _broker_id: current_topics,
    )


def test_broker_evaluation_reports_a_topic_that_was_never_observed(tmp_path) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'missing.db'}")
    broker_id = uuid4()
    item = _expectation(broker_id)
    evaluator = _service(database, item, _metadata())

    report = evaluator.evaluate_broker(broker_id, evaluated_at=NOW)

    assert report.observation_health.status is HealthStatus.HEALTHY
    assert report.observation_health.findings == ()
    assert report.topic_findings[0].failure_code == "TOPIC_NEVER_OBSERVED"
    assert report.topic_findings[0].status is HealthStatus.UNKNOWN
    assert report.aggregate_status is HealthStatus.UNKNOWN
    assert report.evidence_complete is False
    database.dispose()


def test_broker_evaluation_does_not_treat_a_stale_value_as_condition_evidence(
    tmp_path,
) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'stale.db'}")
    broker_id = uuid4()
    item = _expectation(broker_id)
    stale_message = TopicMessage(
        broker_id=broker_id,
        topic="devices/status",
        payload=b"offline",
        qos=0,
        retain=False,
        received_at=NOW - timedelta(seconds=61),
        payload_size=7,
        message_count=1,
        observation_id=uuid4(),
    )
    evaluator = _service(
        database,
        item,
        _metadata(),
        (CurrentTopic(stale_message, ObservationStatus.LIVE),),
    )

    report = evaluator.evaluate_broker(
        broker_id,
        stale_after_seconds=60,
        evaluated_at=NOW,
    )

    assert report.topic_findings[0].failure_code == "TOPIC_STALE"
    assert report.topic_findings[0].status is HealthStatus.UNKNOWN
    assert report.topic_findings[0].evidence_complete is False
    database.dispose()


def test_observation_failures_are_separate_from_topic_findings(tmp_path) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'transport.db'}")
    broker_id = uuid4()
    item = _expectation(broker_id)
    evaluator = _service(
        database,
        item,
        _metadata(
            connection_status=ConnectionStatus.DISCONNECTED,
            observation_started_at=None,
            dropped_message_count=2,
            recording_failure_count=1,
            subscription_rejected_count=1,
        ),
        subscriptions=(),
    )

    report = evaluator.evaluate_broker(broker_id, evaluated_at=NOW)

    codes = {finding.code for finding in report.observation_health.findings}
    assert codes == {
        ObservationFindingCode.BROKER_DISCONNECTED,
        ObservationFindingCode.OBSERVATION_NOT_STARTED,
        ObservationFindingCode.DROPPED_MESSAGES,
        ObservationFindingCode.RECORDING_FAILURES,
        ObservationFindingCode.SUBSCRIPTION_UNAVAILABLE,
        ObservationFindingCode.SUBSCRIPTION_REJECTED,
    }
    assert report.observation_health.status is HealthStatus.PROBLEM
    assert report.topic_findings[0].failure_code == "SUBSCRIPTION_UNAVAILABLE"
    assert report.aggregate_status is HealthStatus.PROBLEM
    assert report.evidence_complete is False
    database.dispose()


def test_broker_target_is_evaluated_without_a_topic_message(tmp_path) -> None:
    database = DatabaseContext(f"sqlite:///{tmp_path / 'broker-target.db'}")
    broker_id = uuid4()
    item = HealthExpectation(
        expectation_id=uuid4(),
        revision=1,
        enabled=True,
        severity=HealthSeverity.CRITICAL,
        target=BrokerTarget(broker_id),
        condition=EqualCondition("connected"),
        actions=frozenset(),
    )
    evaluator = _service(database, item, _metadata())

    report = evaluator.evaluate_broker(broker_id, evaluated_at=NOW)

    assert report.topic_findings[0].status is HealthStatus.HEALTHY
    assert report.aggregate_status is HealthStatus.HEALTHY
    assert report.evidence_complete is True
    database.dispose()


async def test_health_monitor_evaluates_on_its_lifecycle_schedule() -> None:
    broker_id = uuid4()
    report = MagicMock()
    evaluator = MagicMock()
    evaluator.evaluate_broker.return_value = report
    monitor = BrokerHealthMonitor(
        evaluator,
        lambda: (broker_id,),
        interval_seconds=0.01,
    )

    await monitor.start()
    for _ in range(10):
        if evaluator.evaluate_broker.called:
            break
        await asyncio.sleep(0.005)
    await monitor.stop()

    evaluator.evaluate_broker.assert_called_with(
        broker_id,
        stale_after_seconds=300.0,
    )
    assert monitor.latest_reports == {broker_id: report}
