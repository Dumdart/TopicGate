from uuid import UUID

from sqlalchemy import ForeignKey, Table, Column, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from topicgate.infrastructure.database.base import Base
from topicgate.infrastructure.database.models.subscription_row import (
    SubscriptionRow,
)


workspace_subscription = Table(
    "workspace_subscription",
    Base.metadata,
    Column("workspace_id", ForeignKey("observer_workspace.id"), primary_key=True),
    Column("subscription_id", ForeignKey("subscription.id"), primary_key=True),
)


class ObserverWorkspaceRow(Base):
    __tablename__ = "observer_workspace"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("broker_profile.id"),
        unique=True,
    )
    subscriptions: Mapped[list[SubscriptionRow]] = relationship(
        secondary=workspace_subscription,
        cascade="all, delete",
        single_parent=True,
        order_by=SubscriptionRow.id,
    )
    profile: Mapped["BrokerProfileRow"] = relationship(back_populates="workspace")


from topicgate.infrastructure.database.models.broker_profile_row import (  # noqa: E402
    BrokerProfileRow,
)
