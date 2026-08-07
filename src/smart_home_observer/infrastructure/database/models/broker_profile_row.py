from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from smart_home_observer.infrastructure.database.base import Base
from smart_home_observer.infrastructure.database.models.mqtt_config_row import MqttConfigRow


class BrokerProfileRow(Base):
    __tablename__ = "broker_profile"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    position: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    mqtt_config_id: Mapped[int] = mapped_column(
        ForeignKey(MqttConfigRow.id),
        unique=True,
    )
    config: Mapped[MqttConfigRow] = relationship(
        cascade="all, delete-orphan",
        single_parent=True,
    )
    workspace: Mapped["ObserverWorkspaceRow"] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )


from smart_home_observer.infrastructure.database.models.observer_workspace_row import (  # noqa: E402
    ObserverWorkspaceRow,
)
