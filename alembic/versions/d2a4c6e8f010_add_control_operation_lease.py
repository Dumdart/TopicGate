"""Add cross-process control operation lease.

Revision ID: d2a4c6e8f010
Revises: b84d61a9c2e7
Create Date: 2026-08-20 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2a4c6e8f010"
down_revision: Union[str, Sequence[str], None] = "b84d61a9c2e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the singleton lease used by desktop and MCP control mode."""
    state = op.create_table(
        "control_operation_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_control_operation_state_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.bulk_insert(state, [{"id": 1, "generation": 0}])
    op.create_table(
        "control_operation_lease",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner", sa.String(length=32), nullable=False),
        sa.Column("operation", sa.String(length=128), nullable=False),
        sa.Column("token", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_control_operation_lease_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Remove the cross-process control lease."""
    op.drop_table("control_operation_lease")
    op.drop_table("control_operation_state")
