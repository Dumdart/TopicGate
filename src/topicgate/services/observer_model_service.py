from copy import copy
from collections.abc import Iterable, Iterator

from topicgate.core.mqtt_topics import validate_topic_size_and_depth
from topicgate.core.models.observer_model import (
    ObserverModel,
    TopicNode,
    TopicState,
)


class ObserverModelService:
    @staticmethod
    def deep_copy(model: ObserverModel) -> ObserverModel:
        """Return an independent snapshot of the observer model."""
        state_copies: dict[int, TopicState] = {}

        def copy_state(state: TopicState | None) -> TopicState | None:
            if state is None:
                return None
            state_id = id(state)
            if state_id not in state_copies:
                state_copies[state_id] = copy(state)
            return state_copies[state_id]

        root_copies: list[TopicNode] = []
        # Check node identities so malformed cyclic graphs cannot loop forever.
        node_copies: dict[int, TopicNode] = {}
        pending: list[tuple[TopicNode, TopicNode]] = []
        for root in model.root_stats:
            root_copy = TopicNode(root.segment, copy_state(root.state))
            root_copies.append(root_copy)
            node_copies[id(root)] = root_copy
            pending.append((root, root_copy))

        while pending:
            original, copied = pending.pop()
            for key, child in original.children.items():
                child_copy = node_copies.get(id(child))
                if child_copy is None:
                    child_copy = TopicNode(
                        child.segment, copy_state(child.state)
                    )
                    node_copies[id(child)] = child_copy
                    pending.append((child, child_copy))
                copied.children[key] = child_copy

        topic_states = {
            topic: copy_state(state)
            for topic, state in model.topic_states.items()
        }
        return ObserverModel(root_stats=root_copies, topic_states=topic_states)

    @staticmethod
    def get_all_topics(model: ObserverModel) -> list[str]:
        """Return all leaf topic paths that the observer should subscribe to."""
        return [
            topic
            for topic, node in ObserverModelService._scan_nodes(model)
            if not node.children
        ]

    @staticmethod
    def get_all_nodes(model: ObserverModel) -> list[TopicNode]:
        """Return every node in deterministic depth-first order."""
        return [node for _, node in ObserverModelService._scan_nodes(model)]

    @staticmethod
    def get_all_states(model: ObserverModel) -> list[TopicState]:
        """Return the current state for every received topic."""
        states = dict(model.topic_states)
        for _, node in ObserverModelService._scan_nodes(model):
            if node.state is not None:
                states.setdefault(node.state.topic, node.state)
        return list(states.values())

    @staticmethod
    def find_node(model: ObserverModel, topic: str) -> TopicNode | None:
        """Return the node for an exact MQTT topic path, if it is configured."""
        return next(
            (
                node
                for node_topic, node in ObserverModelService._scan_nodes(model)
                if node_topic == topic
            ),
            None,
        )

    @staticmethod
    def find_or_create_node(model: ObserverModel, topic: str) -> TopicNode:
        """Return the exact topic node, creating its path when first observed."""
        segments = validate_topic_size_and_depth(topic, "topic")
        root = next(
            (node for node in model.root_stats if node.segment == segments[0]),
            None,
        )
        if root is None:
            root = TopicNode(segment=segments[0])
            model.root_stats.append(root)

        node = root
        for segment in segments[1:]:
            child = node.children.get(segment)
            if child is None:
                child = TopicNode(segment=segment)
                node.children[segment] = child
            node = child

        return node

    @staticmethod
    def add_topics(model: ObserverModel, topics: Iterable[str]) -> ObserverModel:
        """Add topic paths to an observer tree and return the updated model."""
        for topic in topics:
            ObserverModelService.find_or_create_node(model, topic)
        return model

    @staticmethod
    def _scan_nodes(model: ObserverModel) -> Iterator[tuple[str, TopicNode]]:
        pending = [
            (root, root.segment) for root in reversed(model.root_stats)
        ]
        visited: set[int] = set()
        while pending:
            node, topic = pending.pop()
            if id(node) in visited:
                continue
            visited.add(id(node))
            yield topic, node
            for child in reversed(tuple(node.children.values())):
                pending.append((child, f"{topic}/{child.segment}"))
