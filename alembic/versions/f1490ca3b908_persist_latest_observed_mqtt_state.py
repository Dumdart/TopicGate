"""Persist latest observed MQTT state

Revision ID: f1490ca3b908
Revises: 93fa5748f4b5
Create Date: 2026-08-15 11:08:02.781757

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1490ca3b908"
down_revision: Union[str, Sequence[str], None] = "93fa5748f4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "mqtt_message",
        sa.Column("broker_id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("qos", sa.Integer(), nullable=False),
        sa.Column("retain", sa.Boolean(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_size", sa.Integer(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["broker_id"],
            ["broker_profile.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("broker_id", "topic"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("mqtt_message")
