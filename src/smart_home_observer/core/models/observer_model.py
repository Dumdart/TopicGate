from dataclasses import dataclass, field
from datetime import datetime

from smart_home_observer.core.models.mqtt_state import MqttState

@dataclass
class TopicState:
    name: str
    topic: str
    payload: bytes
    qos: int
    retain: bool
    recieved_at: datetime

@dataclass
class TopicNode:
    segment: str
    state: TopicState | None = None
    children: dict[str, "TopicNode"] = field(default_factory=dict)

@dataclass
class ObserverModel(MqttState):
    root_stats: list[TopicNode]
    topic_states: dict[str, TopicState] = field(default_factory=dict)
