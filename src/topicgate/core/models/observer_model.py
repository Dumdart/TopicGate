from dataclasses import dataclass, field

from topicgate.core.models.mqtt_observation import MqttObservation
from topicgate.core.models.mqtt_state import MqttState


# Check compatibility for callers migrating from the former presentation name.
TopicState = MqttObservation


@dataclass
class TopicNode:
    segment: str
    state: MqttObservation | None = None
    children: dict[str, "TopicNode"] = field(default_factory=dict)


@dataclass
class ObserverModel(MqttState):
    root_stats: list[TopicNode]
    topic_states: dict[str, MqttObservation] = field(default_factory=dict)
    configured_topics: set[str] = field(default_factory=set)
