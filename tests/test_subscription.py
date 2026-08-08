import pytest

from topicgate.core.models.subscription import Subscription


def test_subscription_rejects_malformed_wildcards() -> None:
    with pytest.raises(ValueError, match="# must occupy"):
        Subscription("home/device#")

    with pytest.raises(ValueError, match="# is only valid"):
        Subscription("home/#/value")

    with pytest.raises(ValueError, match=r"\+ must occupy"):
        Subscription("home/device+/value")
