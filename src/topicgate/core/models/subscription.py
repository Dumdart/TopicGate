from dataclasses import dataclass

from topicgate.core.mqtt_topics import validate_topic_size_and_depth


@dataclass(frozen=True)
class Subscription:
    """Editable MQTT subscription options."""

    topic_filter: str
    qos: int = 1
    retain_as_published: bool = False
    retain_handling: int = 0
    id: int | None = None

    def __post_init__(self) -> None:
        segments = validate_topic_size_and_depth(
            self.topic_filter, "topic filter"
        )
        if any("#" in segment and segment != "#" for segment in segments):
            raise ValueError("# must occupy an entire topic level.")
        if "#" in segments and segments[-1] != "#":
            raise ValueError("# is only valid in the final topic level.")
        if any("+" in segment and segment != "+" for segment in segments):
            raise ValueError("+ must occupy an entire topic level.")
        if self.qos not in (0, 1, 2):
            raise ValueError("QoS must be 0, 1, or 2.")
        if self.retain_handling not in (0, 1, 2):
            raise ValueError("Retain handling must be 0, 1, or 2.")
