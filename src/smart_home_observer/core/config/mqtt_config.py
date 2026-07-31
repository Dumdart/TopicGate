from dataclasses import dataclass

@dataclass(frozen=True)
class MqttConfig:
    host: str
    port: int
    username: str
    password: str
    base_topic: str
    use_tls: bool = False
