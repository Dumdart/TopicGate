from uuid import UUID

from sqlalchemy import select

from topicgate.core.models.health import HealthExpectation
from topicgate.core.models.health import TopicTarget
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.database.mappers.health_expectation_mapper import (
    HealthExpectationMapper,
)
from topicgate.infrastructure.database.models.health_expectation_row import (
    HealthExpectationRow,
)


class HealthExpectationRepository:
    def __init__(self, db: DatabaseContext) -> None:
        self._db = db

    def get(self, expectation_id: UUID) -> HealthExpectation | None:
        with self._db.session() as session:
            row = session.get(HealthExpectationRow, expectation_id)
            return None if row is None else HealthExpectationMapper.to_model(row)

    def list_for_topic(
        self,
        broker_id: UUID,
        topic: str,
    ) -> tuple[HealthExpectation, ...]:
        with self._db.session() as session:
            rows = session.scalars(select(HealthExpectationRow)).all()
        matches = []
        for row in rows:
            expectation = HealthExpectationMapper.to_model(row)
            target = expectation.target
            if (
                isinstance(target, TopicTarget)
                and target.broker_id == broker_id
                and target.topic == topic
            ):
                matches.append(expectation)
        return tuple(matches)

    def create(self, expectation: HealthExpectation) -> HealthExpectation:
        with self._db.transaction() as session:
            if session.get(HealthExpectationRow, expectation.expectation_id):
                raise ValueError(
                    f"Health expectation {expectation.expectation_id} already exists."
                )
            session.add(HealthExpectationMapper.to_row(expectation))
        return expectation

    def upsert(self, expectation: HealthExpectation) -> HealthExpectation:
        with self._db.transaction() as session:
            session.merge(HealthExpectationMapper.to_row(expectation))
        return expectation

    def delete(self, expectation_id: UUID) -> None:
        with self._db.transaction() as session:
            row = session.get(HealthExpectationRow, expectation_id)
            if row is None:
                raise KeyError(f"Unknown health expectation: {expectation_id}")
            session.delete(row)
