from dataclasses import dataclass
from uuid import UUID

from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.observer_workspace import ObserverWorkspace


@dataclass
class BrokerProfile:
    id: UUID
    name: str
    config: MqttConfig

    workspace_id: UUID
    workspace: ObserverWorkspace
