from copy import deepcopy
from collections.abc import Iterable, Iterator

from smart_home_observer.core.models.observer_model import (
    ObserverModel,
    TopicNode,
    TopicState,
)


class ObserverModelService:
    @staticmethod
    def deep_copy(model: ObserverModel) -> ObserverModel:
        """Return an independent snapshot of the observer model."""
        return deepcopy(model)

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
        segments = topic.split("/")
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
        for root in model.root_stats:
            yield from ObserverModelService._scan_node(root, root.segment)

    @staticmethod
    def _scan_node(node: TopicNode, topic: str) -> Iterator[tuple[str, TopicNode]]:
        yield topic, node

        for child in node.children.values():
            child_topic = f"{topic}/{child.segment}"
            yield from ObserverModelService._scan_node(child, child_topic)
