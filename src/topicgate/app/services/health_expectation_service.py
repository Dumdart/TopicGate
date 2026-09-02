from topicgate.core.models.topic_message import TopicMessage


class HealthExpectationService:
    def __init__(self) -> None:
       pass

    def evaluate_observation(self, topic_msg: TopicMessage) -> None:  ...
