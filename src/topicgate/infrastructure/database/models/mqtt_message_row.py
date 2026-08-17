from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from topicgate.infrastructure.database.base import Base


class MqttMessageRow(Base):
    __tablename__ = "mqtt_message"

    broker_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("broker_profile.id", ondelete="CASCADE"),
        primary_key=True,
    )
    topic: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[bytes] = mapped_column(LargeBinary)
    qos: Mapped[int] = mapped_column(Integer)
    retain: Mapped[bool] = mapped_column(Boolean)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload_size: Mapped[int] = mapped_column(Integer)
    message_count: Mapped[int] = mapped_column(Integer)
    observation_id: Mapped[UUID] = mapped_column(Uuid)
