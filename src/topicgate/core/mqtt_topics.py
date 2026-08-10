MAX_MQTT_TOPIC_BYTES = 65_535
MAX_MQTT_TOPIC_LEVELS = 128


def validate_topic_size_and_depth(topic: str, kind: str) -> list[str]:
    if not topic:
        raise ValueError(f"A {kind} is required.")
    if "\0" in topic:
        raise ValueError(f"A {kind} cannot contain a null character.")
    if len(topic.encode("utf-8")) > MAX_MQTT_TOPIC_BYTES:
        raise ValueError(
            f"A {kind} cannot exceed {MAX_MQTT_TOPIC_BYTES:,} UTF-8 bytes."
        )

    segments = topic.split("/")
    if len(segments) > MAX_MQTT_TOPIC_LEVELS:
        raise ValueError(
            f"A {kind} cannot exceed {MAX_MQTT_TOPIC_LEVELS} levels."
        )
    return segments


def validate_topic_name(topic: str) -> list[str]:
    segments = validate_topic_size_and_depth(topic, "topic name")
    if "+" in topic or "#" in topic:
        raise ValueError("A topic name cannot contain wildcard characters.")
    return segments
