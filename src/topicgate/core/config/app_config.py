from dataclasses import dataclass
from .mqtt_config import MqttConfig

@dataclass
class AppConfig:
    mqtt: MqttConfig
    id: int | None = None
