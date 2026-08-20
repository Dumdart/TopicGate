from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from topicgate.app.models.broker_snapshot import (
    BrokerSnapshot,
    SnapshotPayloadEncoding,
    SnapshotTopicState,
)
from topicgate.app.services.broker_snapshot_service import (
    MAX_SNAPSHOT_RESULT_LIMIT,
    BrokerSnapshotService,
)
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
from topicgate.presentation.snapshot_presentation import (
    datetime_label,
    duration_label,
    limitation_label,
)


class DashboardSnapshotBuilder:
    """Map shared broker snapshots into dashboard presentation state."""

    def __init__(
        self,
        runtime: TopicGateRuntime,
        snapshot_service: BrokerSnapshotService,
    ) -> None:
        self._runtime = runtime
        self._snapshot_service = snapshot_service

    def snapshot(
        self,
        preferred_path: str = "",
        *,
        broker_snapshot: BrokerSnapshot | None = None,
    ) -> dict[str, Any]:
        active = self._runtime.active_broker
        broker_snapshot = broker_snapshot or self._build_snapshot(active.id)
        subscriptions = tuple(self._runtime.list_subscriptions(active.id))
        observed = tuple(item.topic for item in broker_snapshot.topics)
        visible_topics = tuple(
            item
            for item in broker_snapshot.topics
            if any(
                mqtt_filter_matches(subscription.topic_filter, item.topic)
                for subscription in subscriptions
            )
        )
        visible_names = tuple(item.topic for item in visible_topics)
        paths = collect_visible_topic_paths(subscriptions, observed)
        brokers = [
            broker_display_summary(
                item,
                active.id,
                self._runtime.get_connection_status(item.id),
            )
            for item in self._runtime.list_brokers()
        ]
        default_path = (
            visible_names[0]
            if visible_names
            else subscriptions[0].topic_filter
            if subscriptions
            else ""
        )
        tree_rows = self._tree_rows(
            paths,
            subscriptions,
            visible_topics,
        )
        selectable_paths = {
            row["path"] for row in tree_rows if row["selectable"]
        }
        initial_path = (
            preferred_path
            if preferred_path in selectable_paths
            else default_path
        )
        completeness = asdict(broker_snapshot.completeness)
        completeness["status_label"] = (
            "Complete" if broker_snapshot.completeness.is_complete else "Limited"
        )
        completeness["limitations_labels"] = [
            limitation_label(item)
            for item in broker_snapshot.completeness.limitations
        ]
        return {
            "active_broker_id": str(broker_snapshot.broker.id),
            "active_broker_name": broker_snapshot.broker.name,
            "connection_status": broker_snapshot.connection_status,
            "connection_status_label": (
                broker_snapshot.connection_status.replace("_", " ").title()
            ),
            "captured_at": broker_snapshot.captured_at.isoformat(),
            "captured_at_label": datetime_label(
                broker_snapshot.captured_at
            ),
            "observation_started_at": (
                None
                if broker_snapshot.observation_started_at is None
                else broker_snapshot.observation_started_at.isoformat()
            ),
            "observation_started_at_label": datetime_label(
                broker_snapshot.observation_started_at
            ),
            "observed_for_seconds": broker_snapshot.observed_for_seconds,
            "observed_for_label": duration_label(
                broker_snapshot.observed_for_seconds
            ),
            "dropped_message_count": broker_snapshot.dropped_message_count,
            "brokers": [self._broker_dict(item) for item in brokers],
            "subscriptions": [
                self._subscription_row(item) for item in subscriptions
            ],
            "topics": [
                self._topic_row(item) for item in visible_topics
            ],
            "tree_rows": tree_rows,
            "freshness": asdict(broker_snapshot.freshness),
            "results": asdict(broker_snapshot.results),
            "completeness": completeness,
            "initial_selection": self._selection(
                broker_snapshot,
                subscriptions,
                initial_path,
            ),
        }

    def broker_control(self, broker_id: UUID) -> dict[str, Any]:
        broker = self._runtime.get_broker(broker_id)
        active_id = self._runtime.active_broker.id
        summary = broker_display_summary(
            broker,
            active_id,
            self._runtime.get_connection_status(broker_id),
        )
        status = summary.connection_status
        is_active = broker_id == active_id
        can_disconnect = is_active and status in {
            "connecting",
            "connected",
            "reconnecting",
        }
        can_reconnect_observe = not is_active or status in {
            "disconnected",
            "connected",
            "reconnecting",
        }
        result = self._broker_dict(summary)
        result.update(
            {
                "selected_broker_id": str(broker_id),
                "can_connect": not is_active or status == "disconnected",
                "can_reconnect_observe": can_reconnect_observe,
                "can_disconnect": can_disconnect,
                "connect_disabled": is_active and status != "disconnected",
                "reconnect_observe_disabled": not can_reconnect_observe,
                "disconnect_disabled": not can_disconnect,
            }
        )
        return result

    def selection(self, broker_id: UUID, path: str) -> dict[str, Any]:
        broker_snapshot = self._build_snapshot(broker_id)
        subscriptions = tuple(self._runtime.list_subscriptions(broker_id))
        return self._selection(broker_snapshot, subscriptions, path)

    def _build_snapshot(self, broker_id: UUID) -> BrokerSnapshot:
        return self._snapshot_service.build_current(
            broker_id,
            result_limit=MAX_SNAPSHOT_RESULT_LIMIT,
        )

    @staticmethod
    def _selection(
        broker_snapshot: BrokerSnapshot,
        subscriptions: tuple[Subscription, ...],
        path: str,
    ) -> dict[str, Any]:
        subscription = matching_subscription(subscriptions, path)
        state = next(
            (item for item in broker_snapshot.topics if item.topic == path),
            None,
        )
        return {
            "path": path or "No topic selected",
            "topic": DashboardSnapshotBuilder._topic_detail(
                state,
                path,
                broker_snapshot.dropped_message_count,
            ),
            "subscription": asdict(subscription_detail(subscription)),
        }

    @staticmethod
    def _topic_detail(
        state: SnapshotTopicState | None,
        topic: str,
        dropped_message_count: int,
    ) -> dict[str, Any]:
        result = asdict(topic_detail(state, topic, dropped_message_count))
        result["age_seconds_label"] = result["age_label"]
        return result

    @staticmethod
    def _topic_row(state: SnapshotTopicState) -> dict[str, Any]:
        preview = state.payload.value
        if state.payload.encoding == SnapshotPayloadEncoding.BASE64:
            preview = f"Base64: {preview[:48]}"
        elif len(preview) > 64:
            preview = f"{preview[:61]}..."
        return {
            "topic": state.topic,
            "qos": str(state.qos),
            "retain_label": "Yes" if state.retain else "No",
            "payload_preview": preview,
            "received_at": state.received_at.isoformat(timespec="seconds"),
            "age_seconds": state.age_seconds,
            "source": state.source.value,
            "status": state.status.value,
            "is_truncated": state.payload.truncated,
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
        topics: tuple[SnapshotTopicState, ...],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        status_by_topic = {item.topic: item.status.value for item in topics}
        observed = tuple(status_by_topic)

        def append(nodes: tuple[Any, ...], depth: int) -> None:
            for node in nodes:
                rows.append(
                    {
                        "label": node.label,
                        "path": node.path,
                        "indent": f"{depth * 1.15}rem",
                        "selectable": node.selectable,
                        "has_children": bool(node.children),
                        "status": status_by_topic.get(node.path),
                    }
                )
                append(node.children, depth + 1)

        append(build_topic_tree(paths, subscriptions, observed, topics), 0)
        return rows
