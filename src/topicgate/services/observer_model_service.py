from copy import copy
from collections.abc import Iterable, Iterator

from topicgate.core.mqtt_topics import validate_topic_size_and_depth
from topicgate.core.observer_limits import (
    MAX_OBSERVER_NODES,
    ObserverModelCapacityError,
)
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
        return ObserverModel(
            root_stats=root_copies,
            topic_states=topic_states,
            configured_topics=set(model.configured_topics),
        )

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
        missing_nodes = ObserverModelService._missing_node_count(model, segments)
        if (
            len(ObserverModelService.get_all_nodes(model)) + missing_nodes
            > MAX_OBSERVER_NODES
        ):
            raise ObserverModelCapacityError(
                f"An observer model cannot exceed {MAX_OBSERVER_NODES:,} nodes."
            )
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
            model.configured_topics.add(topic)
        return model

    @staticmethod
    def remove_topic(model: ObserverModel, topic: str) -> TopicState | None:
        """Remove retained state and prune its unconfigured empty path."""
        state = model.topic_states.pop(topic, None)
        segments = topic.split("/")
        chain: list[tuple[TopicNode | None, TopicNode, str]] = []
        node = next(
            (root for root in model.root_stats if root.segment == segments[0]),
            None,
        )
        if node is None:
            return state

        path = segments[0]
        chain.append((None, node, path))
        for segment in segments[1:]:
            parent = node
            node = parent.children.get(segment)
            if node is None:
                return state
            path = f"{path}/{segment}"
            chain.append((parent, node, path))

        node.state = None
        # Check from the leaf upward so shared and configured paths remain.
        for parent, current, current_path in reversed(chain):
            if (
                current.children
                or current.state is not None
                or current_path in model.configured_topics
            ):
                break
            if parent is None:
                model.root_stats.remove(current)
            else:
                parent.children.pop(current.segment, None)
        return state

    @staticmethod
    def rebuild(
        model: ObserverModel,
        configured_topics: Iterable[str],
    ) -> None:
        """Rebuild bounded structural nodes from configuration and retained state."""
        rebuilt = ObserverModel(
            root_stats=[],
            topic_states=dict(model.topic_states),
        )
        ObserverModelService.add_topics(rebuilt, configured_topics)
        for state in rebuilt.topic_states.values():
            node = ObserverModelService.find_or_create_node(rebuilt, state.topic)
            node.state = state
        model.root_stats = rebuilt.root_stats
        model.configured_topics = rebuilt.configured_topics

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

    @staticmethod
    def _missing_node_count(model: ObserverModel, segments: list[str]) -> int:
        node = next(
            (root for root in model.root_stats if root.segment == segments[0]),
            None,
        )
        if node is None:
            return len(segments)
        for index, segment in enumerate(segments[1:], start=1):
            child = node.children.get(segment)
            if child is None:
                return len(segments) - index
            node = child
        return 0
