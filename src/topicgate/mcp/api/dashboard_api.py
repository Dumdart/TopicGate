from __future__ import annotations

from base64 import b64encode
from datetime import datetime
from typing import Any
from uuid import UUID

from fastmcp import FastMCP

from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.core.models.mqtt_observation import MqttObservation
from topicgate.core.models.subscription import Subscription
from topicgate.core.mqtt_topics import mqtt_filter_matches
from topicgate.mcp.api.mcp_api import MCPApi
from topicgate.mcp.api.dashboard_snapshot import DashboardSnapshotBuilder

try:
    from fastmcp import FastMCPApp
    from prefab_ui.actions import SetState, ShowToast
    from prefab_ui.actions.mcp import CallTool, RequestDisplayMode
    from prefab_ui.app import PrefabApp
    from prefab_ui.components import (
        Button,
        Column,
        Div,
        Else,
        ForEach,
        Grid,
        Heading,
        Icon,
        If,
        Label,
        Row,
        Select,
        SelectOption,
        Text,
    )
    from prefab_ui.rx import EVENT, RESULT, STATE
except ImportError:
    FastMCPApp = None  # type: ignore[assignment,misc]


class DashboardAPI(MCPApi):
    """Read-only FastMCP companion dashboard for the TopicGate runtime."""

    def __init__(self, runtime: TopicGateRuntime):
        self._runtime = runtime
        self._snapshot_builder = DashboardSnapshotBuilder(runtime)
        self._app: Any | None = None
        self.open_topicgate_dashboard: Any | None = None

        if FastMCPApp is not None:
            self._app = FastMCPApp("topicgate-dashboard")
            self._register_app_tools()

    def register(self, mcp: FastMCP, *, control_enabled: bool = False) -> None:
        if control_enabled and self._app is not None:
            mcp.add_provider(self._app)

    def _register_app_tools(self) -> None:
        app = self._app

        @app.tool()
        async def activate_dashboard_broker(broker_id: str) -> dict[str, Any]:
            """Activate a broker and return its current dashboard snapshot.

            Side effects: Disconnects the current client, changes the active broker,
            connects over MQTT, and starts receiving messages.
            Required state: The profile and credentials must permit a connection.
            Identifiers: broker_id must be a broker UUID from the dashboard snapshot.
            Failures: Fails for invalid UUIDs, unknown profiles, or connection errors.
            """
            await self._runtime.activate_broker(UUID(broker_id))
            return self._snapshot()

        @app.tool()
        def select_dashboard_path(path: str) -> dict[str, Any]:
            """Read dashboard details for a subscription filter or observed topic.

            Side effects: None; this only derives a view from current local state.
            Required state: An active broker profile must exist.
            Identifiers: path is an MQTT topic or subscription filter from the tree.
            Failures: Fails without an active profile or when local state cannot be read.
            """
            return self._selection(self._runtime.active_broker.id, path)

        @app.ui(
            name="open_topicgate_dashboard",
            title="Open TopicGate dashboard",
            description=(
                "Open the TopicGate broker monitoring dashboard. Side effects: "
                "opening the view is passive, but switching brokers inside it activates "
                "and connects that profile. Required state: an active broker and local "
                "database must be available. Identifiers: broker choices use profile "
                "UUIDs and tree paths use MQTT topics or filters. Failures: opening or "
                "interaction can fail for missing state, invalid identifiers, database "
                "errors, or MQTT connection errors."
            ),
        )
        def open_topicgate_dashboard() -> PrefabApp:
            """Open the TopicGate monitoring dashboard described by the tool metadata."""
            return self._build_dashboard(
                activate_broker=activate_dashboard_broker,
                select_path=select_dashboard_path,
            )

        self.open_topicgate_dashboard = open_topicgate_dashboard
        self._activate_dashboard_broker = activate_dashboard_broker
        self._select_dashboard_path = select_dashboard_path

    def _snapshot(self) -> dict[str, Any]:
        return self._snapshot_builder.snapshot()

    def _build_dashboard(self, **tools: Any) -> PrefabApp:
        snapshot = self._snapshot()

        with Column(
            gap=0,
            css_class=(
                "min-h-screen bg-[#f3f4f6] text-[#202124] "
                "font-sans selection:bg-[#4b5563]/20"
            ),
        ) as view:
            self._build_header(snapshot, tools)
            with Grid(
                columns=None,
                gap=0,
                css_class=(
                    "grid-cols-1 lg:grid-cols-[21rem_minmax(0,1fr)] "
                    "min-h-[calc(100vh-5.75rem)] border-t border-[#c8ced6]"
                ),
            ):
                self._build_tree(tools)
                self._build_details()

        return PrefabApp(
            title="TopicGate",
            view=view,
            mode="light",
            on_mount=RequestDisplayMode("fullscreen"),
            state={
                "snapshot": snapshot,
                "selection": snapshot["initial_selection"],
            },
        )

    def _build_header(self, snapshot: dict[str, Any], tools: dict[str, Any]) -> None:
        with Row(
            gap=5,
            align="center",
            justify="between",
            css_class="min-h-[5.75rem] bg-[#ffffff] px-6 lg:px-8 flex-wrap",
        ):
            Heading(
                "TopicGate",
                level=1,
                css_class="text-2xl font-semibold tracking-[-0.035em]",
            )
            with Div(css_class="w-full sm:w-[40rem] sm:max-w-[55vw]"):
                Label(
                    "Broker",
                    css_class="sr-only",
                )
                with Select(
                    name="active_broker_id",
                    value=snapshot["active_broker_id"],
                    on_change=CallTool(
                        tools["activate_broker"],
                        arguments={"broker_id": EVENT},
                        on_success=[
                            SetState("snapshot", RESULT),
                            SetState("selection", RESULT.initial_selection),
                        ],
                        on_error=ShowToast(
                            "Could not switch broker", variant="error"
                        ),
                    ),
                    css_class=(
                        "h-11 border-[#b8c0ca] bg-[#ffffff] "
                        "text-sm text-[#202124]"
                    ),
                ):
                    for broker in snapshot["brokers"]:
                        SelectOption(
                            broker["label"],
                            value=broker["id"],
                            selected=broker["id"] == snapshot["active_broker_id"],
                        )
            with Row(gap=2, align="center", css_class="min-w-28 justify-end"):
                with If("snapshot.connection_status == 'connected'"):
                    Div(css_class="size-2 rounded-full bg-[#4b5563]")
                with Else():
                    Div(css_class="size-2 rounded-full bg-[#202124]/35")
                Text(
                    f"{STATE.snapshot.connection_status_label}",
                    css_class="text-sm text-[#202124]/70",
                )

    def _build_tree(self, tools: dict[str, Any]) -> None:
        with Column(
            gap=0,
            css_class=(
                "border-b border-[#c8ced6] bg-[#ffffff] px-4 py-7 "
                "lg:border-b-0 lg:border-r lg:px-5 lg:py-8"
            ),
        ):
            Heading(
                "Subscriptions",
                level=2,
                css_class="mb-5 px-2 text-xl font-medium tracking-tight",
            )
            with If("snapshot.tree_rows.length > 0"):
                with Column(
                    gap=0,
                    css_class=(
                        "max-h-[22rem] overflow-auto "
                        "lg:max-h-[calc(100vh-11rem)]"
                    ),
                ):
                    with ForEach("snapshot.tree_rows") as item:
                        with Div(style={"paddingLeft": f"{item.indent}"}):
                            with If(item.selectable):
                                with If(item.path == STATE.selection.path):
                                    self._build_tree_button(
                                        item,
                                        tools,
                                        selected=True,
                                    )
                                with Else():
                                    self._build_tree_button(
                                        item,
                                        tools,
                                        selected=False,
                                    )
                            with Else():
                                with Row(
                                    gap=2,
                                    align="center",
                                    css_class="h-9 px-2 text-[#202124]/70",
                                ):
                                    Icon("chevron-down", css_class="size-4")
                                    Text(
                                        f"{item.label}",
                                        css_class="font-mono text-[13px]",
                                    )
            with Else():
                Text(
                    "No subscriptions configured for this broker.",
                    css_class="px-2 text-sm leading-6 text-[#202124]/55",
                )

    @staticmethod
    def _build_tree_button(
        item: Any,
        tools: dict[str, Any],
        *,
        selected: bool,
    ) -> None:
        selected_class = (
            "border-l-[#405d7a] bg-[#dce9f7] text-[#202124]"
            if selected
            else "border-l-transparent text-[#202124]/75"
        )
        Button(
            f"{item.label}",
            variant="ghost",
            size="sm",
            icon="circle-small",
            on_click=CallTool(
                tools["select_path"],
                arguments={"path": item.path},
                on_success=SetState("selection", RESULT),
                on_error=ShowToast("Could not load topic", variant="error"),
            ),
            css_class=(
                "h-9 w-full justify-start rounded-none border-l-2 px-2 "
                "font-mono text-[13px] font-normal hover:border-l-[#9aa8b6] "
                f"hover:bg-[#eef2f6] hover:text-[#202124] {selected_class}"
            ),
        )

    def _build_details(self) -> None:
        with Column(
            gap=0,
            css_class="min-w-0 px-6 py-8 lg:px-12 lg:py-12 xl:px-16",
        ):
            Text(
                f"{STATE.selection.path}",
                code=True,
                css_class=(
                    "mb-5 break-all text-sm leading-6 text-[#4b5563] "
                    "lg:text-base"
                ),
            )
            with Div(
                css_class=(
                    "min-h-44 rounded-lg border border-[#c8ced6] border-l-4 "
                    "border-l-[#405d7a] bg-[#fbfcfd] "
                    "px-8 py-8 lg:min-h-52 lg:px-10 lg:py-10"
                )
            ):
                Text(
                    f"{STATE.selection.topic.payload_display}",
                    code=True,
                    css_class=(
                        "max-h-56 overflow-auto whitespace-pre-wrap break-words "
                        "text-3xl font-normal leading-tight text-[#202124] lg:text-5xl"
                    ),
                )

            with Grid(
                columns=None,
                gap=0,
                css_class=(
                    "mt-10 grid-cols-1 rounded-lg border border-[#c8ced6] "
                    "bg-[#ffffff] px-8 py-8 xl:grid-cols-2 "
                    "xl:divide-x xl:divide-[#c8ced6]"
                ),
            ):
                self._build_metadata()
                self._build_subscription_settings()

    def _build_metadata(self) -> None:
        with Column(gap=4, css_class="pb-9 xl:pr-12"):
            Heading(
                "Metadata",
                level=2,
                css_class=(
                    "mb-1 text-xs font-semibold uppercase tracking-[0.18em] "
                    "text-[#4b5563]"
                ),
            )
            self._detail_row("Encoding", STATE.selection.topic.payload_encoding)
            self._detail_row("QoS", STATE.selection.topic.qos)
            self._detail_row("Retained", STATE.selection.topic.retain_label)
            self._detail_row("Last seen", STATE.selection.topic.received_at)
            self._detail_row("Payload size", STATE.selection.topic.payload_size_label)
            self._detail_row("Message count", STATE.selection.topic.message_count)
            self._detail_row(
                "Dropped messages", STATE.selection.topic.dropped_message_count
            )

    def _build_subscription_settings(self) -> None:
        with Column(gap=4, css_class="border-t border-[#c8ced6] pt-9 xl:border-t-0 xl:pl-12"):
            Heading(
                "Subscription",
                level=2,
                css_class=(
                    "mb-1 text-xs font-semibold uppercase tracking-[0.18em] "
                    "text-[#4b5563]"
                ),
            )
            self._detail_row("Filter", STATE.selection.subscription.topic_filter, code=True)
            self._detail_row("QoS", STATE.selection.subscription.qos_label)
            self._detail_row(
                "Retain", STATE.selection.subscription.retain_as_published_label
            )
            self._detail_row(
                "Handling", STATE.selection.subscription.retain_handling_label
            )

    @staticmethod
    def _detail_row(label: str, value: Any, *, code: bool = False) -> None:
        with Grid(columns=2, gap=3, css_class="grid-cols-[8rem_minmax(0,1fr)] text-sm"):
            Text(label, css_class="text-[#5f6368]")
            Text(
                f"{value}",
                code=code,
                css_class="min-w-0 break-words text-[#202124]/85",
            )

    def _selection(self, broker_id: UUID, path: str) -> dict[str, Any]:
        return self._snapshot_builder.selection(broker_id, path)

    def _matching_subscription(
        self,
        broker_id: UUID,
        path: str,
    ) -> Subscription | None:
        subscriptions = tuple(self._runtime.list_subscriptions(broker_id))
        exact = next(
            (
                subscription
                for subscription in subscriptions
                if subscription.topic_filter == path
            ),
            None,
        )
        if exact is not None:
            return exact
        matches = [
            subscription
            for subscription in subscriptions
            if mqtt_filter_matches(subscription.topic_filter, path)
        ]
        if not matches:
            return None
        return max(
            matches,
            key=lambda item: len(
                item.topic_filter.replace("#", "").replace("+", "")
            ),
        )

    @staticmethod
    def _default_path(
        subscriptions: tuple[Subscription, ...],
        topics: tuple[str, ...],
    ) -> str:
        if topics:
            return topics[0]
        if subscriptions:
            return subscriptions[0].topic_filter
        return ""

    @staticmethod
    def _tree_rows(
        subscriptions: tuple[Subscription, ...],
        topics: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        root: dict[str, dict[str, Any]] = {}
        subscription_paths = {item.topic_filter for item in subscriptions}
        topic_paths = set(topics)

        for full_path in sorted(subscription_paths | topic_paths, key=str.casefold):
            children = root
            partial: list[str] = []
            for segment in full_path.split("/"):
                partial.append(segment)
                path = "/".join(partial)
                node = children.setdefault(
                    segment,
                    {
                        "label": segment or "/",
                        "path": path,
                        "children": {},
                    },
                )
                children = node["children"]

        rows: list[dict[str, Any]] = []

        def append_rows(nodes: dict[str, dict[str, Any]], depth: int) -> None:
            for key in sorted(nodes, key=str.casefold):
                node = nodes[key]
                path = node["path"]
                children = node["children"]
                rows.append(
                    {
                        "label": node["label"],
                        "path": path,
                        "indent": f"{depth * 1.15}rem",
                        "selectable": (
                            path in subscription_paths or path in topic_paths
                        ),
                        "has_children": bool(children),
                    }
                )
                append_rows(children, depth + 1)

        append_rows(root, 0)
        return rows

    @staticmethod
    def _broker_row(broker: Any) -> dict[str, Any]:
        scheme = "mqtts" if broker.config.use_tls else "mqtt"
        endpoint = f"{scheme}://{broker.config.host}:{broker.config.port}"
        return {
            "id": str(broker.id),
            "name": broker.name,
            "endpoint": endpoint,
            "label": f"{broker.name} ({endpoint})",
        }

    @staticmethod
    def _subscription_row(subscription: Subscription) -> dict[str, Any]:
        return {
            "topic_filter": subscription.topic_filter,
            "qos": subscription.qos,
            "retain_as_published": subscription.retain_as_published,
            "retain_handling": subscription.retain_handling,
        }

    def _topic_row(self, broker_id: UUID, topic: str) -> dict[str, Any]:
        state = self._runtime.get_topic_state(broker_id, topic)
        if state is None:
            return {
                "topic": topic,
                "qos": "-",
                "retain_label": "-",
                "payload_preview": "",
                "received_at": "-",
            }
        detail = self._topic_detail_from_state(state)
        return {
            "topic": topic,
            "qos": detail["qos"],
            "retain_label": detail["retain_label"],
            "payload_preview": self._payload_preview(state.payload),
            "received_at": detail["received_at"],
        }

    @staticmethod
    def _topic_detail_from_state(state: MqttObservation) -> dict[str, Any]:
        payload_base64 = b64encode(state.payload).decode("ascii")
        try:
            payload_text = state.payload.decode("utf-8")
            payload_display = payload_text
            payload_encoding = "UTF-8"
        except UnicodeDecodeError:
            payload_text = "Payload is not valid UTF-8."
            payload_display = payload_base64
            payload_encoding = "Base64"
        payload_size = state.payload_size or len(state.payload)
        payload_size_label = (
            f"{payload_size} byte" if payload_size == 1 else f"{payload_size} bytes"
        )
        return {
            "topic": state.topic,
            "has_value": True,
            "qos": state.qos,
            "retain_label": "Yes" if state.retain else "No",
            "received_at": DashboardAPI._format_datetime(state.recieved_at),
            "message_count": state.message_count,
            "payload_size": payload_size,
            "payload_size_label": payload_size_label,
            "payload_text": payload_text,
            "payload_base64": payload_base64,
            "payload_display": payload_display,
            "payload_encoding": payload_encoding,
        }

    @staticmethod
    def _empty_topic_detail(topic: str = "") -> dict[str, Any]:
        return {
            "topic": topic,
            "has_value": False,
            "qos": "-",
            "retain_label": "-",
            "received_at": "-",
            "message_count": 0,
            "payload_size": 0,
            "payload_size_label": "-",
            "payload_text": "",
            "payload_base64": "",
            "payload_display": "No value observed",
            "payload_encoding": "-",
        }

    @staticmethod
    def _subscription_detail(
        subscription: Subscription | None,
    ) -> dict[str, Any]:
        if subscription is None:
            return {
                "topic_filter": "No matching subscription",
                "qos_label": "-",
                "retain_as_published_label": "-",
                "retain_handling_label": "-",
            }
        return {
            "topic_filter": subscription.topic_filter,
            "qos_label": {
                0: "0 · At most once",
                1: "1 · At least once",
                2: "2 · Exactly once",
            }[subscription.qos],
            "retain_as_published_label": (
                "Preserve retained flag"
                if subscription.retain_as_published
                else "Rewrite retained flag"
            ),
            "retain_handling_label": {
                0: "Send retained messages",
                1: "Only for a new subscription",
                2: "Do not send retained messages",
            }[subscription.retain_handling],
        }

    @staticmethod
    def _payload_preview(payload: bytes) -> str:
        try:
            preview = payload.decode("utf-8")
        except UnicodeDecodeError:
            return f"Base64: {b64encode(payload).decode('ascii')[:48]}"
        return preview if len(preview) <= 64 else f"{preview[:61]}..."

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        return value.astimezone().isoformat(timespec="seconds")
