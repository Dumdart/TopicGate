"""Initial revision

Revision ID: 93fa5748f4b5
Revises: 
Create Date: 2026-08-15 10:42:50.777383

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "93fa5748f4b5"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "mqtt_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("host", sa.String(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("use_tls", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "subscription",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("topic_filter", sa.String(), nullable=False),
        sa.Column("qos", sa.Integer(), nullable=False),
        sa.Column("retain_as_published", sa.Boolean(), nullable=False),
        sa.Column("retain_handling", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "app_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mqtt_config_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["mqtt_config_id"], ["mqtt_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mqtt_config_id"),
    )
    op.create_table(
        "broker_profile",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("mqtt_config_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["mqtt_config_id"], ["mqtt_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mqtt_config_id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "observer_workspace",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["broker_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id"),
    )
    op.create_table(
        "workspace_subscription",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscription.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["observer_workspace.id"]),
        sa.PrimaryKeyConstraint("workspace_id", "subscription_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("workspace_subscription")
    op.drop_table("observer_workspace")
    op.drop_table("broker_profile")
    op.drop_table("app_config")
    op.drop_table("subscription")
    op.drop_table("mqtt_config")
