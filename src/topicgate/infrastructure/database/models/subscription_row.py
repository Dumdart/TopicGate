from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import mapped_column, Mapped
from topicgate.infrastructure.database.base import Base

class SubscriptionRow(Base):
    __tablename__ = "subscription"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_filter: Mapped[str] = mapped_column(String)
    qos: Mapped[int] = mapped_column(Integer)
    retain_as_published: Mapped[bool] = mapped_column(Boolean)
    retain_handling: Mapped[int] = mapped_column(Integer)

    def __init__(self, topic_filter: str, qos: int = 1, retain_as_published: bool = False, retain_handling: int = 0):
        self.topic_filter = topic_filter
        self.qos = qos
        self.retain_as_published = retain_as_published
        self.retain_handling = retain_handling
