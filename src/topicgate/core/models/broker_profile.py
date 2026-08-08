from dataclasses import dataclass
from uuid import UUID

from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.observer_workspace import ObserverWorkspace


@dataclass
class BrokerProfile:
    id: UUID
    name: str
    config: MqttConfig

    workspace_id: UUID
    workspace: ObserverWorkspace
