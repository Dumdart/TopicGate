from contextlib import AbstractContextManager
from typing import Protocol
from uuid import UUID

from topicgate.core.models.health import ExpectationFailure
from topicgate.core.models.health import ExpectationState
from topicgate.core.models.health import HealthExpectation


class HealthExpectationReader(Protocol):
    def list_for_topic(
        self,
        broker_id: UUID,
        topic: str,
    ) -> tuple[HealthExpectation, ...]: ...


class ExpectationStateStore(Protocol):
    def get(
        self,
        expectation_id: UUID,
        *,
        transaction: object | None = None,
    ) -> ExpectationState | None: ...

    def upsert(
        self,
        state: ExpectationState,
        *,
        transaction: object | None = None,
    ) -> ExpectationState: ...


class ExpectationFailureStore(Protocol):
    def get(
        self,
        failure_id: UUID,
        *,
        transaction: object | None = None,
    ) -> ExpectationFailure | None: ...

    def upsert(
        self,
        failure: ExpectationFailure,
        *,
        transaction: object | None = None,
    ) -> ExpectationFailure: ...


class TransactionManager(Protocol):
    def transaction(self) -> AbstractContextManager[object]: ...
