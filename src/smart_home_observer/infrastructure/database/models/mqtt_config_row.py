from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import mapped_column, Mapped
from smart_home_observer.infrastructure.database.base import Base


class MqttConfigRow(Base):
    __tablename__ = 'mqtt_config'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host: Mapped[str] = mapped_column(String)
    port: Mapped[int] = mapped_column(Integer)
    username: Mapped[str] = mapped_column(String)
    use_tls: Mapped[bool] = mapped_column(Boolean)

    def __init__(self, host: str, port: int, username: str, use_tls: bool):
        self.host = host
        self.port = port
        self.username = username
        self.use_tls = use_tls
