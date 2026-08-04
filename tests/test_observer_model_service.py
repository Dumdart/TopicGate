from datetime import datetime, timezone

from smart_home_observer.core.models.observer_model import TopicState
from smart_home_observer.services.observer_model_service import ObserverModelService
from smart_home_observer.services.topic_service import TopicService


def test_get_all_topics_returns_configured_leaf_topic_paths() -> None:
    model = TopicService.get_topics()

    assert ObserverModelService.get_all_topics(model) == [
        "SmartHome/Huehnerstall/door/command",
        "SmartHome/Huehnerstall/door/status",
        "SmartHome/Huehnerstall/door/status_code",
        "SmartHome/Huehnerstall/door/fault",
        "SmartHome/Huehnerstall/door/connected",
        "SmartHome/Huehnerstall/door/battery",
        "SmartHome/Huehnerstall/door/light_level",
    ]


def test_get_all_nodes_returns_branches_and_leaf_nodes() -> None:
    model = TopicService.get_topics()

    nodes = ObserverModelService.get_all_nodes(model)

    assert [node.segment for node in nodes[:4]] == [
        "SmartHome",
        "Huehnerstall",
        "door",
        "command",
    ]
    assert len(nodes) == 10


def test_get_all_states_and_find_node_scan_the_same_tree() -> None:
    model = TopicService.get_topics()
    state = TopicState(
        name="Door status",
        topic="SmartHome/Huehnerstall/door/status",
        payload=b"open",
        qos=1,
        retain=True,
        recieved_at=datetime.now(timezone.utc),
    )
    status_node = ObserverModelService.find_node(model, state.topic)

    assert status_node is not None
    status_node.state = state

    assert ObserverModelService.get_all_states(model) == [state]
    assert ObserverModelService.find_node(model, "SmartHome/missing") is None


def test_deep_copy_returns_an_independent_observer_model() -> None:
    original = TopicService.get_topics()

    copied = ObserverModelService.deep_copy(original)
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
