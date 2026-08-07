from dataclasses import dataclass


@dataclass(frozen=True)
class Subscription:
    """Editable MQTT subscription options."""

    topic_filter: str
    qos: int = 1
    retain_as_published: bool = False
    retain_handling: int = 0
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.topic_filter:
            raise ValueError("A topic filter is required.")
        if "\0" in self.topic_filter:
            raise ValueError("A topic filter cannot contain a null character.")
        if len(self.topic_filter.encode("utf-8")) > 65_535:
            raise ValueError("A topic filter cannot exceed 65,535 UTF-8 bytes.")
        segments = self.topic_filter.split("/")
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
