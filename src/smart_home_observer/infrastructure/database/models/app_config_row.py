from smart_home_observer.infrastructure.database.base import Base
from smart_home_observer.infrastructure.database.models.mqtt_config_row import MqttConfigRow
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship



class AppConfigRow(Base):
    __tablename__ = 'app_config'
    id: Mapped[int] = mapped_column(primary_key=True)
    mqtt_config_id: Mapped[int] = mapped_column(
        ForeignKey(MqttConfigRow.id),
        unique=True
    )
    mqtt_config_row: Mapped[MqttConfigRow] = relationship()

    def __init__(self, mqtt_config_row: MqttConfigRow):
        self.mqtt_config_row = mqtt_config_row
