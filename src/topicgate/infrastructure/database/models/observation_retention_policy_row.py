from sqlalchemy import Boolean, CheckConstraint, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from topicgate.infrastructure.database.base import Base


class ObservationRetentionPolicyRow(Base):
    __tablename__ = "observation_retention_policy"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_retention_policy_singleton"),
        CheckConstraint(
            "max_entries_per_broker > 0",
            name="ck_retention_policy_broker_entries_positive",
        ),
        CheckConstraint(
            "max_entries_total > 0",
            name="ck_retention_policy_total_entries_positive",
        ),
        CheckConstraint(
            "max_entries_per_broker <= max_entries_total",
            name="ck_retention_policy_entry_limits_ordered",
        ),
        CheckConstraint(
            "warning_threshold > 0 AND warning_threshold <= 1",
            name="ck_retention_policy_warning_threshold",
        ),
        CheckConstraint(
            "max_payload_bytes_per_topic > 0",
            name="ck_retention_policy_topic_payload_positive",
        ),
        CheckConstraint(
            "max_payload_bytes_per_broker > 0",
            name="ck_retention_policy_broker_payload_positive",
        ),
        CheckConstraint(
            "max_payload_bytes_per_topic <= max_payload_bytes_per_broker",
            name="ck_retention_policy_payload_limits_ordered",
        ),
        CheckConstraint(
            "max_database_bytes > 0",
            name="ck_retention_policy_database_bytes_positive",
        ),
        CheckConstraint(
            "max_age_seconds IS NULL OR max_age_seconds > 0",
            name="ck_retention_policy_age_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    max_entries_per_broker: Mapped[int] = mapped_column(Integer)
    max_entries_total: Mapped[int] = mapped_column(Integer)
    warning_threshold: Mapped[float] = mapped_column(Float)
    max_payload_bytes_per_topic: Mapped[int] = mapped_column(Integer)
    max_payload_bytes_per_broker: Mapped[int] = mapped_column(Integer)
    max_database_bytes: Mapped[int] = mapped_column(Integer)
    max_age_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auto_remove_expired: Mapped[bool] = mapped_column(Boolean)
    auto_remove_excess: Mapped[bool] = mapped_column(Boolean)
    auto_remove_unsubscribed: Mapped[bool] = mapped_column(Boolean)
