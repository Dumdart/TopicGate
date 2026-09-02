from abc import ABC
from dataclasses import dataclass
from uuid import UUID

from topicgate.core.mqtt_topics import validate_topic_name


class ExpectationTarget(ABC):
    pass


@dataclass
class BrokerTarget(ExpectationTarget):
    broker_id: UUID


@dataclass
class TopicTarget(ExpectationTarget):
    def __init__(self, broker_id: UUID, topic: str) -> None:
        self.broker_id = broker_id
        try:
            validate_topic_name(topic)
            self.topic = topic
        except Exception as error:
            assert f"Invalid topic. Exception: {error}"

    broker_id: UUID
    topic: str
