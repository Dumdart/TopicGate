from dataclasses import dataclass, field
from datetime import datetime

from topicgate.core.models.mqtt_state import MqttState

@dataclass
class TopicState:
    name: str
    topic: str
    payload: bytes
    qos: int
    retain: bool
    recieved_at: datetime
    message_count: int = 1
    payload_size: int | None = None

    def __post_init__(self) -> None:
        self.payload_size = max(self.payload_size or 0, len(self.payload))

@dataclass
class TopicNode:
    segment: str
    state: TopicState | None = None
    children: dict[str, "TopicNode"] = field(default_factory=dict)

@dataclass
class ObserverModel(MqttState):
    root_stats: list[TopicNode]
    topic_states: dict[str, TopicState] = field(default_factory=dict)
