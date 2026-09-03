import logging
from dataclasses import replace
from datetime import datetime

from topicgate.core.interfaces.health_repositories import (
    ExpectationFailureStore,
    ExpectationStateStore,
    HealthExpectationReader,
    TransactionManager,
)
from topicgate.core.models.health import (
    ConditionResult,
    ExpectationEvaluation,
    ExpectationFailure,
    ExpectationState,
    HealthExpectation,
    HealthStatus,
    HealthTransition,
)
from topicgate.core.models.health.health_action_context import HealthActionContext
from topicgate.core.models.topic_message import TopicMessage
from topicgate.processors.action_dispatcher import ActionDispatcher
from topicgate.processors.transition_tracker import TransitionTracker

logger = logging.getLogger(__name__)


class HealthExpectationService:
    def __init__(
        self,
        health_expectation_repo: HealthExpectationReader,
        expectation_state_repo: ExpectationStateStore,
        expectation_failure_repo: ExpectationFailureStore,
        transaction_manager: TransactionManager,
        transition_tracker: TransitionTracker,
        action_dispatcher: ActionDispatcher,
    ) -> None:
        self._expectation_repo = health_expectation_repo
        self._state_repo = expectation_state_repo
        self._failure_repo = expectation_failure_repo
        self._transaction_manager = transaction_manager
        self._transition_tracker = transition_tracker
        self._action_dispatcher = action_dispatcher

    def evaluate_observation(
        self,
        topic_msg: TopicMessage,
    ) -> tuple[ExpectationEvaluation, ...]:
        try:
            expectations = self._expectation_repo.list_for_topic(
                topic_msg.broker_id,
                topic_msg.topic,
            )
        except Exception:
            logger.exception(
                "Unable to load health expectations for broker %s topic %s.",
                topic_msg.broker_id,
                topic_msg.topic,
            )
            return ()

        evaluations: list[ExpectationEvaluation] = []
        for expectation in expectations:
            if not expectation.enabled:
                continue
            try:
                evaluations.append(self._evaluate(expectation, topic_msg))
            except Exception:
                logger.exception(
                    "Health expectation %s evaluation failed.",
                    expectation.expectation_id,
                )
        return tuple(evaluations)

    def _evaluate(
        self,
        expectation: HealthExpectation,
        topic_msg: TopicMessage,
    ) -> ExpectationEvaluation:
        result = (
            expectation.condition.handle_condition(topic_msg.payload)
            if not topic_msg.is_truncated
            else ConditionResult(
                status=HealthStatus.UNKNOWN,
                evidence_complete=False,
                evidence_summary="Message payload was truncated."
            )
        )

        evaluation = self._condition_result_to_evaluation(
            result,
            expectation,
            topic_msg.received_at,
        )

        with self._transaction_manager.transaction() as transaction:
            previous_state = self._state_repo.get(
                expectation.expectation_id,
                transaction=transaction,
            )

            state, transition = self._transition_tracker.apply(
                previous_state,
                evaluation,
            )
            failure = self._update_failure(
                evaluation,
                previous_state,
                state,
                transition,
                transaction=transaction,
            )
            if failure is not None:
                self._failure_repo.upsert(failure, transaction=transaction)
            self._state_repo.upsert(state, transaction=transaction)

        if transition not in {
            HealthTransition.NEW_FAILURE,
            HealthTransition.RECOVERY,
        }:
            return evaluation
        self._action_dispatcher.dispatch(
            action_kinds=expectation.actions,
            context=HealthActionContext(
                evaluation=evaluation,
                transition=transition,
                severity=expectation.severity,
                failure=failure,
            ),
        )
        return evaluation

    @staticmethod
    def _condition_result_to_evaluation(
        condition_result: ConditionResult,
        expectation: HealthExpectation,
        evaluated_at: datetime,
    ) -> ExpectationEvaluation:
        return ExpectationEvaluation(
            expectation_id=expectation.expectation_id,
            expectation_revision=expectation.revision,
            status=condition_result.status,
            evaluated_at=evaluated_at,
            failure_code=condition_result.failure_code,
            evidence_summary=condition_result.evidence_summary,
            evidence_complete=condition_result.evidence_complete,
        )

    def _update_failure(
        self,
        evaluation: ExpectationEvaluation,
        previous_state: ExpectationState | None,
        state: ExpectationState,
        transition: HealthTransition | None,
        *,
        transaction: object,
    ) -> ExpectationFailure | None:
        if transition is HealthTransition.NEW_FAILURE:
            if state.active_failure_id is None:
                raise RuntimeError("New failure transition has no failure ID.")
            return ExpectationFailure(
                failure_id=state.active_failure_id,
                expectation_id=evaluation.expectation_id,
                first_failed_at=evaluation.evaluated_at,
                last_seen_at=evaluation.evaluated_at,
                occurrence_count=1,
                expected_revision=evaluation.expectation_revision,
                last_healthy_at=state.last_healthy_at,
                failure_code=evaluation.failure_code,
                evidence_summary=evaluation.evidence_summary,
            )

        previous_failure_id = (
            None if previous_state is None else previous_state.active_failure_id
        )
        if previous_failure_id is None:
            return None
        failure = self._failure_repo.get(
            previous_failure_id,
            transaction=transaction,
        )
        if failure is None:
            raise RuntimeError(
                f"Active health failure {previous_failure_id} was not found."
            )
        if transition is HealthTransition.ONGOING_FAILURE:
            return replace(
                failure,
                last_seen_at=evaluation.evaluated_at,
                occurrence_count=failure.occurrence_count + 1,
                expected_revision=evaluation.expectation_revision,
                failure_code=evaluation.failure_code,
                evidence_summary=evaluation.evidence_summary,
            )
        if transition is HealthTransition.RECOVERY:
            return replace(
                failure,
                last_seen_at=evaluation.evaluated_at,
                last_healthy_at=evaluation.evaluated_at,
                recovered_at=evaluation.evaluated_at,
            )
        return None
