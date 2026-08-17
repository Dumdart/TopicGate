from sqlalchemy import select

from topicgate.core.models.observation_retention_policy import (
    ObservationRetentionPolicy,
)
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.database.mappers.observation_retention_policy_mapper import (
    ObservationRetentionPolicyMapper,
)
from topicgate.infrastructure.database.models.observation_retention_policy_row import (
    ObservationRetentionPolicyRow,
)


class ObservationRetentionPolicyRepository:
    """Persist the application-wide MQTT observation retention policy."""

    def __init__(self, db: DatabaseContext) -> None:
        self._db = db

    def get(self) -> ObservationRetentionPolicy:
        with self._db.session() as session:
            row = session.scalar(
                select(ObservationRetentionPolicyRow).where(
                    ObservationRetentionPolicyRow.id == 1
                )
            )
            if row is None:
                raise RuntimeError("The observation retention policy is missing.")
            return ObservationRetentionPolicyMapper.to_policy(row)

    def update(
        self,
        policy: ObservationRetentionPolicy,
    ) -> ObservationRetentionPolicy:
        with self._db.session() as session:
            row = session.get(ObservationRetentionPolicyRow, 1)
            if row is None:
                raise RuntimeError("The observation retention policy is missing.")
            ObservationRetentionPolicyMapper.apply(policy, row)
            session.commit()
            return policy
