from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.core.models.subscription import Subscription
from topicgate.core.mqtt_topics import mqtt_filter_matches
from topicgate.presentation.topic_presentation import (
    broker_display_summary,
    build_topic_tree,
    collect_visible_topic_paths,
    matching_subscription,
    subscription_detail,
    topic_detail,
)


class DashboardSnapshotBuilder:
    """Build dashboard JSON state without depending on Prefab components."""

    def __init__(self, runtime: TopicGateRuntime) -> None:
        self._runtime = runtime

    def snapshot(self) -> dict[str, Any]:
        active = self._runtime.active_broker
        broker_id = active.id
        subscriptions = tuple(self._runtime.list_subscriptions(broker_id))
        observed = tuple(self._runtime.list_topics())
        visible_topics = tuple(
            topic
            for topic in observed
            if any(
                mqtt_filter_matches(item.topic_filter, topic)
                for item in subscriptions
            )
        )
        paths = collect_visible_topic_paths(subscriptions, observed)
        status = self._runtime.connection_status
        brokers = [
            broker_display_summary(item, broker_id, status)
            for item in self._runtime.list_brokers()
        ]
        return {
            "active_broker_id": str(broker_id),
            "active_broker_name": active.name,
            "connection_status": str(getattr(status, "value", status)).lower(),
            "connection_status_label": str(
                getattr(status, "value", status)
            ).replace("_", " ").title(),
            "brokers": [self._broker_dict(item) for item in brokers],
            "subscriptions": [self._subscription_row(item) for item in subscriptions],
            "topics": [self._topic_row(broker_id, topic) for topic in visible_topics],
            "tree_rows": self._tree_rows(paths, subscriptions, visible_topics),
            "initial_selection": self.selection(
                broker_id,
                visible_topics[0]
                if visible_topics
                else subscriptions[0].topic_filter
                if subscriptions
                else "",
            ),
        }

    def selection(self, broker_id: UUID, path: str) -> dict[str, Any]:
        subscription = matching_subscription(
            self._runtime.list_subscriptions(broker_id),
            path,
        )
        state = self._runtime.get_topic_state(broker_id, path) if path else None
        detail = topic_detail(
            state,
            path,
            self._runtime.dropped_message_count,
        )
        return {
            "path": path or "No topic selected",
            "topic": asdict(detail),
            "subscription": asdict(subscription_detail(subscription)),
        }

    def _topic_row(self, broker_id: UUID, topic: str) -> dict[str, Any]:
        detail = topic_detail(self._runtime.get_topic_state(broker_id, topic), topic)
        preview = detail.payload_display
        if len(preview) > 64:
            preview = f"{preview[:61]}..."
        if detail.payload_encoding == "Base64":
            preview = f"Base64: {detail.payload_base64[:48]}"
        return {
            "topic": topic,
            "qos": detail.qos_label,
            "retain_label": detail.retain_label,
            "payload_preview": preview if detail.has_value else "",
            "received_at": detail.received_at,
        }

    @staticmethod
    def _subscription_row(subscription: Subscription) -> dict[str, Any]:
        return {
            "topic_filter": subscription.topic_filter,
            "qos": subscription.qos,
            "retain_as_published": subscription.retain_as_published,
            "retain_handling": subscription.retain_handling,
        }

    @staticmethod
    def _broker_dict(summary: Any) -> dict[str, Any]:
        result = asdict(summary)
        result["id"] = str(summary.id)
        return result

    @staticmethod
    def _tree_rows(
        paths: tuple[str, ...],
        subscriptions: tuple[Subscription, ...],
        observed: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        def append(nodes: tuple[Any, ...], depth: int) -> None:
            for node in nodes:
                rows.append(
                    {
                        "label": node.label,
                        "path": node.path,
                        "indent": f"{depth * 1.15}rem",
                        "selectable": node.selectable,
                        "has_children": bool(node.children),
                    }
                )
                append(node.children, depth + 1)

        append(build_topic_tree(paths, subscriptions, observed), 0)
        return rows
