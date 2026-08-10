import pytest

from topicgate.core.models.subscription import Subscription
from topicgate.core.mqtt_topics import MAX_MQTT_TOPIC_LEVELS


def test_subscription_rejects_malformed_wildcards() -> None:
    with pytest.raises(ValueError, match="# must occupy"):
        Subscription("home/device#")

    with pytest.raises(ValueError, match="# is only valid"):
        Subscription("home/#/value")

    with pytest.raises(ValueError, match=r"\+ must occupy"):
        Subscription("home/device+/value")


def test_subscription_rejects_excessive_topic_depth() -> None:
    topic_filter = "/".join(
        "level" for _ in range(MAX_MQTT_TOPIC_LEVELS + 1)
    )

    with pytest.raises(ValueError, match="cannot exceed 128 levels"):
        Subscription(topic_filter)
