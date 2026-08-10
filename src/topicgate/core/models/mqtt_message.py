from dataclasses import dataclass


@dataclass
class MqttMessage:
    topic: str
    payload: bytes
    qos: int
    retain: bool
    payload_size: int | None = None

    def __post_init__(self) -> None:
        self.payload_size = max(self.payload_size or 0, len(self.payload))
