from dataclasses import dataclass
from uuid import UUID

from topicgate.core.config.mqtt_config import MqttConfig


@dataclass(frozen=True)
class BrokerSummary:
    """Broker settings safe to expose outside the application runtime."""

    id: UUID
    name: str
    config: MqttConfig
    password_configured: bool
