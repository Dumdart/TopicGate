"""Rename the logical persisted payload byte limit.

Revision ID: b84d61a9c2e7
Revises: 7c3e9f1a2b4d
Create Date: 2026-08-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "b84d61a9c2e7"
down_revision: Union[str, Sequence[str], None] = "7c3e9f1a2b4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Describe the limit as logical persisted payload bytes."""
    op.execute(
        "ALTER TABLE observation_retention_policy "
        "RENAME COLUMN max_database_bytes "
        "TO max_persisted_payload_database_bytes_total"
    )


def downgrade() -> None:
    """Restore the previous retention-policy column name."""
    op.execute(
        "ALTER TABLE observation_retention_policy "
        "RENAME COLUMN max_persisted_payload_database_bytes_total "
        "TO max_database_bytes"
    )
