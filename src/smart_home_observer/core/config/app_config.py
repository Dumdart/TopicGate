from dataclasses import dataclass
from .mqtt_config import MqttConfig

@dataclass(frozen=True)
class AppConfig:
    mqtt: MqttConfig
