"""Add observation retention policy

Revision ID: 7c3e9f1a2b4d
Revises: f1490ca3b908
Create Date: 2026-08-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c3e9f1a2b4d"
down_revision: Union[str, Sequence[str], None] = "f1490ca3b908"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create and seed the application-wide retention policy."""
    policy = op.create_table(
        "observation_retention_policy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("max_entries_per_broker", sa.Integer(), nullable=False),
        sa.Column("max_entries_total", sa.Integer(), nullable=False),
        sa.Column("warning_threshold", sa.Float(), nullable=False),
        sa.Column("max_payload_bytes_per_topic", sa.Integer(), nullable=False),
        sa.Column("max_payload_bytes_per_broker", sa.Integer(), nullable=False),
        sa.Column("max_database_bytes", sa.Integer(), nullable=False),
        sa.Column("max_age_seconds", sa.Integer(), nullable=True),
        sa.Column("auto_remove_expired", sa.Boolean(), nullable=False),
        sa.Column("auto_remove_excess", sa.Boolean(), nullable=False),
        sa.Column("auto_remove_unsubscribed", sa.Boolean(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_retention_policy_singleton"),
        sa.CheckConstraint(
            "max_entries_per_broker > 0",
            name="ck_retention_policy_broker_entries_positive",
        ),
        sa.CheckConstraint(
            "max_entries_total > 0",
            name="ck_retention_policy_total_entries_positive",
        ),
        sa.CheckConstraint(
            "max_entries_per_broker <= max_entries_total",
            name="ck_retention_policy_entry_limits_ordered",
        ),
        sa.CheckConstraint(
            "warning_threshold > 0 AND warning_threshold <= 1",
            name="ck_retention_policy_warning_threshold",
        ),
        sa.CheckConstraint(
            "max_payload_bytes_per_topic > 0",
            name="ck_retention_policy_topic_payload_positive",
        ),
        sa.CheckConstraint(
            "max_payload_bytes_per_broker > 0",
            name="ck_retention_policy_broker_payload_positive",
        ),
        sa.CheckConstraint(
            "max_payload_bytes_per_topic <= max_payload_bytes_per_broker",
            name="ck_retention_policy_payload_limits_ordered",
        ),
        sa.CheckConstraint(
            "max_database_bytes > 0",
            name="ck_retention_policy_database_bytes_positive",
        ),
        sa.CheckConstraint(
            "max_age_seconds IS NULL OR max_age_seconds > 0",
            name="ck_retention_policy_age_positive",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.bulk_insert(
        policy,
        [
            {
                "id": 1,
                "max_entries_per_broker": 1_000,
                "max_entries_total": 10_000,
                "warning_threshold": 0.80,
                "max_payload_bytes_per_topic": 64 * 1024,
                "max_payload_bytes_per_broker": 8 * 1024 * 1024,
                "max_database_bytes": 256 * 1024 * 1024,
                "max_age_seconds": None,
                "auto_remove_expired": True,
                "auto_remove_excess": True,
                "auto_remove_unsubscribed": False,
            }
        ],
    )


def downgrade() -> None:
    """Remove the observation retention policy."""
    op.drop_table("observation_retention_policy")
