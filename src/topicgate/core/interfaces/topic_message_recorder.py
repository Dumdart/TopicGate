from typing import Protocol

from topicgate.core.models.topic_message import TopicMessage


class TopicMessageRecorder(Protocol):
    def record_message(self, entry: TopicMessage) -> None: ...
