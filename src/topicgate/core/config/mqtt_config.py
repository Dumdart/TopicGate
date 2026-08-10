from dataclasses import dataclass

@dataclass(frozen=True)
class MqttConfig:
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = False
    id: int | None = None

    def validate_transport_security(self) -> None:
        if (self.username or self.password) and not self.use_tls:
            raise ValueError(
                "TLS is required when an MQTT username or password is configured."
            )
