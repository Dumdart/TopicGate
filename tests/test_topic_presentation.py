from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from topicgate.core.models.mqtt_observation import MqttObservation as TopicState
from topicgate.core.models.subscription import Subscription
from topicgate.presentation.topic_presentation import (
    build_topic_tree,
    collect_visible_topic_paths,
    matching_subscription,
    subscription_detail,
    topic_detail,
)


def test_visible_paths_and_tree_merge_only_matching_observed_topics() -> None:
    subscriptions = (Subscription("home/#"), Subscription("$SYS/+/load"))
    paths = collect_visible_topic_paths(
        subscriptions,
        ("home/kitchen/temp", "outside/temp", "$SYS/node/load"),
    )
    assert paths == ("$SYS/+/load", "$SYS/node/load", "home/#", "home/kitchen/temp")
    tree = build_topic_tree(paths, subscriptions, ("home/kitchen/temp",))
    assert [node.path for node in tree] == ["$SYS", "home"]
    assert tree[1].selectable is False
    wildcard = next(node for node in tree[1].children if node.label == "#")
    assert wildcard.selectable is True
    assert wildcard.is_wildcard_filter is True
    assert [badge.label for badge in wildcard.badges] == ["Filter"]
    kitchen = next(node for node in tree[1].children if node.label == "kitchen")
    assert kitchen.children[0].is_observed is True


def test_matching_subscription_prefers_exact_then_specific_filter() -> None:
    subscriptions = (
        Subscription("sensors/#"),
        Subscription("sensors/+/temperature"),
        Subscription("sensors/kitchen/temperature"),
    )
    assert matching_subscription(subscriptions, "sensors/kitchen/temperature").topic_filter == "sensors/kitchen/temperature"
    assert matching_subscription(subscriptions[:2], "sensors/kitchen/temperature").topic_filter == "sensors/+/temperature"


def test_topic_detail_identifies_binary_and_formats_json() -> None:
    binary = topic_detail(
        TopicState("image", "camera/image", b"\xff\x00", 1, True, datetime.now(timezone.utc))
    )
    assert binary.payload_encoding == "Base64"
    assert binary.payload_base64 == "/wA="
    assert binary.retain_label == "Yes"
    json_detail = topic_detail(
        TopicState("state", "device/state", b'{"open":true}', 0, False, datetime.now(timezone.utc))
    )
    assert json_detail.decoded_payload == '{\n  "open": true\n}'


def test_presentation_models_are_immutable() -> None:
    detail = subscription_detail(Subscription("home/#"))
    with pytest.raises(FrozenInstanceError):
        detail.topic_filter = "changed/#"  # type: ignore[misc]
