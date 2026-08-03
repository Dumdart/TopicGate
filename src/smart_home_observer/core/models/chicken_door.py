from dataclasses import dataclass

from smart_home_observer.core.models.mqtt_state import MqttState

@dataclass
class ChickenDoor(MqttState):
    command: str
    status: str
    status_code: int
    fault: str
    connected: bool
    battery: int
    light_level: int
