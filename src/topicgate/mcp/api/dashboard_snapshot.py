from __future__ import annotations

from base64 import b64decode, b64encode
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

    def snapshot(self) -> dict[str, Any]:
        active = self._runtime.active_broker
        broker_snapshot = self._build_snapshot(active.id)
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
                broker_snapshot.connection_status,
            )
            for item in self._runtime.list_brokers()
        ]
        initial_path = (
            visible_names[0]
            if visible_names
            else subscriptions[0].topic_filter
            if subscriptions
            else ""
        )
        return {
            "active_broker_id": str(broker_snapshot.broker.id),
            "active_broker_name": broker_snapshot.broker.name,
            "connection_status": broker_snapshot.connection_status,
            "connection_status_label": (
                broker_snapshot.connection_status.replace("_", " ").title()
            ),
            "captured_at": broker_snapshot.captured_at.isoformat(),
            "brokers": [self._broker_dict(item) for item in brokers],
            "subscriptions": [
                self._subscription_row(item) for item in subscriptions
            ],
            "topics": [
                self._topic_row(item) for item in visible_topics
            ],
            "tree_rows": self._tree_rows(
                paths,
                subscriptions,
                visible_names,
            ),
            "freshness": asdict(broker_snapshot.freshness),
            "results": asdict(broker_snapshot.results),
            "completeness": asdict(broker_snapshot.completeness),
            "initial_selection": self._selection(
                broker_snapshot,
                subscriptions,
                initial_path,
            ),
        }

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
        if state is None:
            return {
                "topic": topic,
                "has_value": False,
                "payload_text": "",
                "payload_base64": "",
                "decoded_payload": "Waiting for a message",
                "raw_payload": "-",
                "payload_display": "No value observed",
                "payload_encoding": "-",
                "payload_size": 0,
                "payload_size_label": "-",
                "rendered_payload_size": 0,
                "is_truncated": False,
                "truncation_label": "",
                "qos": None,
                "qos_label": "-",
                "retained": None,
                "retain_label": "-",
                "received_at": "-",
                "age_seconds": None,
                "age_seconds_label": "-",
                "message_count": 0,
                "dropped_message_count": dropped_message_count,
                "source": None,
                "source_label": "-",
                "ingestion_truncated": False,
                "rendering_truncated": False,
            }

        payload = state.payload
        is_utf8 = payload.encoding == SnapshotPayloadEncoding.UTF8
        payload_text = (
            payload.value if is_utf8 else "Payload is not valid UTF-8."
        )
        payload_base64 = (
            b64encode(payload.value.encode("utf-8")).decode("ascii")
            if is_utf8
            else payload.value
        )
        rendered_bytes = (
            payload.value.encode("utf-8")
            if is_utf8
            else b64decode(payload.value)
        )
        truncation_label = (
            "Payload truncated: showing "
            f"{payload.rendered_size} of {payload.original_size} bytes"
            if payload.truncated
            else ""
        )
        return {
            "topic": state.topic,
            "has_value": True,
            "payload_text": payload_text,
            "payload_base64": payload_base64,
            "decoded_payload": payload.value,
            "raw_payload": rendered_bytes.hex(" "),
            "payload_display": payload.value,
            "payload_encoding": "UTF-8" if is_utf8 else "Base64",
            "payload_size": payload.original_size,
            "payload_size_label": DashboardSnapshotBuilder._size_label(
                payload.original_size
            ),
            "rendered_payload_size": payload.rendered_size,
            "is_truncated": payload.truncated,
            "truncation_label": truncation_label,
            "qos": state.qos,
            "qos_label": str(state.qos),
            "retained": state.retain,
            "retain_label": "Yes" if state.retain else "No",
            "received_at": state.received_at.isoformat(timespec="seconds"),
            "age_seconds": state.age_seconds,
            "age_seconds_label": f"{state.age_seconds:.1f} seconds",
            "message_count": state.message_count,
            "dropped_message_count": dropped_message_count,
            "source": state.source.value,
            "source_label": state.source.value.title(),
            "ingestion_truncated": payload.ingestion_truncated,
            "rendering_truncated": payload.rendering_truncated,
        }

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
            "is_truncated": state.payload.truncated,
        }

    @staticmethod
    def _size_label(size: int) -> str:
        return f"{size} byte" if size == 1 else f"{size} bytes"

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
