from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from topicgate.infrastructure.database.base import Base


class ExpectationFailureRow(Base):
    __tablename__ = "expectation_failure"

    failure_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    expectation_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("health_expectation.expectation_id", ondelete="CASCADE"),
    )
    first_failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    occurrence_count: Mapped[int] = mapped_column(Integer, default=0)
    expected_revision: Mapped[int] = mapped_column(Integer, default=0)
    last_healthy_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_code: Mapped[str | None] = mapped_column(String, nullable=True)
    evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
