from datetime import datetime, timezone
from unittest.mock import patch

from topicgate.core.models.observer_model import (
    ObserverModel,
    TopicNode,
    TopicState,
)
from topicgate.processors.observer_model_processor import ObserverModelProcessor


TOPIC_PATHS = [
    "SmartHome/Huehnerstall/door/command",
    "SmartHome/Huehnerstall/door/status",
    "SmartHome/Huehnerstall/door/status_code",
    "SmartHome/Huehnerstall/door/fault",
    "SmartHome/Huehnerstall/door/connected",
    "SmartHome/Huehnerstall/door/battery",
    "SmartHome/Huehnerstall/door/light_level",
]


def build_model() -> ObserverModel:
    return ObserverModelProcessor.add_topics(
        ObserverModel(root_stats=[]),
        TOPIC_PATHS,
    )


def test_get_all_topics_returns_configured_leaf_topic_paths() -> None:
    model = build_model()

    assert ObserverModelProcessor.get_all_topics(model) == TOPIC_PATHS


def test_get_all_nodes_returns_branches_and_leaf_nodes() -> None:
    model = build_model()

    nodes = ObserverModelProcessor.get_all_nodes(model)

    assert [node.segment for node in nodes[:4]] == [
        "SmartHome",
        "Huehnerstall",
        "door",
        "command",
    ]
    assert len(nodes) == 10


def test_get_all_states_and_find_node_scan_the_same_tree() -> None:
    model = build_model()
    state = TopicState(
        name="Door status",
        topic="SmartHome/Huehnerstall/door/status",
        payload=b"open",
        qos=1,
        retain=True,
        recieved_at=datetime.now(timezone.utc),
    )
    status_node = ObserverModelProcessor.find_node(model, state.topic)

    assert status_node is not None
    status_node.state = state

    assert ObserverModelProcessor.get_all_states(model) == [state]
    assert ObserverModelProcessor.find_node(model, "SmartHome/missing") is None


def test_deep_copy_returns_an_independent_observer_model() -> None:
    original = build_model()

    copied = ObserverModelProcessor.deep_copy(original)
    copied.root_stats[0].children["Huehnerstall"].children["door"].children[
        "status"
    ].segment = "door-status"

    assert copied is not original
    assert copied.root_stats[0] is not original.root_stats[0]
    assert (
        original.root_stats[0].children["Huehnerstall"].children["door"].children[
            "status"
        ].segment
        == "status"
    )


def test_add_topics_builds_shared_observer_tree_paths() -> None:
    model = ObserverModel(root_stats=[])

    result = ObserverModelProcessor.add_topics(
        model,
        [
            "SmartHome/kitchen/status",
            "SmartHome/kitchen/temperature",
            "bridge/#",
        ],
    )

    assert result is model
    assert ObserverModelProcessor.get_all_topics(model) == [
        "SmartHome/kitchen/status",
        "SmartHome/kitchen/temperature",
        "bridge/#",
    ]
    assert len(model.root_stats) == 2
    assert model.configured_topics == {
        "SmartHome/kitchen/status",
        "SmartHome/kitchen/temperature",
        "bridge/#",
    }


def test_add_topics_does_not_duplicate_existing_nodes() -> None:
    model = ObserverModel(root_stats=[])

    ObserverModelProcessor.add_topics(model, ["home/status", "home/status"])

    assert ObserverModelProcessor.get_all_topics(model) == ["home/status"]
    assert len(ObserverModelProcessor.get_all_nodes(model)) == 2


def test_deep_legacy_tree_copy_and_traversal_are_iterative() -> None:
    root = TopicNode("root")
    node = root
    depth = 1_500
    for index in range(1, depth):
        child = TopicNode(str(index))
        node.children[child.segment] = child
        node = child
    model = ObserverModel(root_stats=[root])

    copied = ObserverModelProcessor.deep_copy(model)
    copied_nodes = ObserverModelProcessor.get_all_nodes(copied)

    assert len(copied_nodes) == depth
    assert copied_nodes[-1].segment == str(depth - 1)
    assert copied.root_stats[0] is not root


def test_observer_tree_rejects_nodes_beyond_budget_before_mutation() -> None:
    model = ObserverModel(root_stats=[])
    with patch(
        "topicgate.processors.observer_model_processor.MAX_OBSERVER_NODES", 3
    ):
        ObserverModelProcessor.add_topics(model, ["a/b/c"])
        try:
            ObserverModelProcessor.find_or_create_node(model, "a/b/c/d")
        except ValueError:
            pass
        else:
            raise AssertionError("Expected the observer node budget to apply")

    assert ObserverModelProcessor.get_all_topics(model) == ["a/b/c"]
