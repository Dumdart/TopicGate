from dataclasses import dataclass


@dataclass
class MqttMessage:
    topic: str
    payload: bytes
    qos: int
    retain: bool
