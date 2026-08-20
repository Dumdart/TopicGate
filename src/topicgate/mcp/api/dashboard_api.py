from __future__ import annotations

from typing import Any
from uuid import UUID

from fastmcp import FastMCP

from topicgate.app.models.broker_snapshot import BrokerSnapshot
from topicgate.app.services.broker_snapshot_service import BrokerSnapshotService
from topicgate.app.topicgate_runtime import TopicGateRuntime
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
    """Control-mode dashboard with read-only monitoring and broker activation."""

    def __init__(
        self,
        runtime: TopicGateRuntime,
        snapshot_service: BrokerSnapshotService | None = None,
    ) -> None:
        self._runtime = runtime
        self._snapshot_service = snapshot_service or BrokerSnapshotService(runtime)
        self._snapshot_builder = DashboardSnapshotBuilder(
            runtime,
            self._snapshot_service,
        )
        self._app: Any | None = None
        self.open_topicgate_dashboard: Any | None = None

        if FastMCPApp is not None:
            self._app = FastMCPApp("topicgate-control-dashboard")
            self._register_app_tools()

    def register(self, mcp: FastMCP, *, control_enabled: bool = False) -> None:
        if control_enabled and self._app is not None:
            mcp.add_provider(self._app)

    def _register_app_tools(self) -> None:
        app = self._app

        @app.tool()
        def select_dashboard_broker(broker_id: str) -> dict[str, Any]:
            """Select broker controls without changing MQTT runtime state.

            Side effects: None; broker activation and connection are unchanged.
            Required state: The selected broker profile must exist.
            Identifiers: broker_id must be a broker UUID from the dashboard snapshot.
            Failures: Fails for invalid UUIDs or unknown profiles.
            """
            return self._broker_control(UUID(broker_id))

        @app.tool()
        async def connect_dashboard_broker(
            broker_id: str,
            selected_path: str = "",
        ) -> dict[str, Any]:
            """Connect the selected broker and return refreshed dashboard state.

            Side effects: Activates an inactive profile or connects the disconnected
            active MQTT client.
            Required state: The profile and credentials must permit a connection.
            Identifiers: broker_id is a dashboard broker UUID; selected_path is an
            MQTT topic or filter to preserve when it remains available.
            Failures: Fails for invalid identifiers, unknown profiles, or connection
            errors.
            """
            target = UUID(broker_id)
            previous_active_id = self._runtime.active_broker.id
            if target != previous_active_id:
                await self._runtime.activate_broker(target)
            else:
                status = self._status_value(
                    self._runtime.get_connection_status(target)
                )
                if status != "disconnected":
                    raise ValueError("The selected broker is not disconnected.")
                await self._runtime.connect()
            return self._dashboard_state(previous_active_id, selected_path)

        @app.tool()
        async def disconnect_dashboard_broker(
            broker_id: str,
            selected_path: str = "",
        ) -> dict[str, Any]:
            """Disconnect the selected active broker and refresh dashboard state.

            Side effects: Disconnects the active MQTT client.
            Required state: The selected profile must be active and connecting,
            connected, or reconnecting.
            Identifiers: broker_id is a dashboard broker UUID; selected_path is an
            MQTT topic or filter to preserve when it remains available.
            Failures: Fails for invalid identifiers, inactive profiles, invalid
            connection state, or disconnect errors.
            """
            target = UUID(broker_id)
            active_id = self._runtime.active_broker.id
            status = self._status_value(
                self._runtime.get_connection_status(target)
            )
            if target != active_id or status not in {
                "connecting",
                "connected",
                "reconnecting",
            }:
                raise ValueError(
                    "Disconnect is available only for the active connected broker."
                )
            await self._runtime.disconnect()
            return self._dashboard_state(active_id, selected_path)

        @app.tool()
        async def reconnect_observe_dashboard_broker(
            broker_id: str,
            selected_path: str = "",
        ) -> dict[str, Any]:
            """Reconnect the selected broker, wait, and capture fresh state.

            Side effects: Activates and reconnects the selected profile, waits the
            default observation interval, and captures a new broker snapshot.
            Required state: The profile and credentials must permit a connection.
            Identifiers: broker_id is a dashboard broker UUID; selected_path is an
            MQTT topic or filter to preserve when it remains available.
            Failures: Fails for invalid identifiers, unknown profiles, connection
            errors, or snapshot capture errors.
            """
            target = UUID(broker_id)
            previous_active_id = self._runtime.active_broker.id
            observed_snapshot = await self._snapshot_service.observe(target)
            return self._dashboard_state(
                previous_active_id,
                selected_path,
                observed_snapshot,
            )

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
            title="Open TopicGate control dashboard",
            description=(
                "Open the TopicGate control-mode monitoring dashboard. Side effects: "
                "opening the view and selecting a broker are passive; explicitly "
                "labeled lifecycle actions can connect, disconnect, reconnect, and "
                "capture observations. This dashboard is unavailable in read-only mode. "
                "Required state: an active broker and local database must be available. "
                "Identifiers: broker choices use profile UUIDs and tree paths use MQTT "
                "topics or filters. Failures: opening or interaction can fail for "
                "missing state, invalid identifiers, database errors, or MQTT connection "
                "errors."
            ),
        )
        def open_topicgate_dashboard() -> PrefabApp:
            """Open the TopicGate monitoring dashboard described by the tool metadata."""
            return self._build_dashboard(
                select_broker=select_dashboard_broker,
                connect_broker=connect_dashboard_broker,
                disconnect_broker=disconnect_dashboard_broker,
                reconnect_observe_broker=reconnect_observe_dashboard_broker,
                select_path=select_dashboard_path,
            )

        self.open_topicgate_dashboard = open_topicgate_dashboard
        self._select_dashboard_broker = select_dashboard_broker
        self._connect_dashboard_broker = connect_dashboard_broker
        self._disconnect_dashboard_broker = disconnect_dashboard_broker
        self._reconnect_observe_dashboard_broker = (
            reconnect_observe_dashboard_broker
        )
        self._select_dashboard_path = select_dashboard_path

    def _snapshot(
        self,
        preferred_path: str = "",
        broker_snapshot: BrokerSnapshot | None = None,
    ) -> dict[str, Any]:
        return self._snapshot_builder.snapshot(
            preferred_path,
            broker_snapshot=broker_snapshot,
        )

    def _broker_control(self, broker_id: UUID) -> dict[str, Any]:
        return self._snapshot_builder.broker_control(broker_id)

    def _dashboard_state(
        self,
        previous_active_id: UUID,
        selected_path: str,
        broker_snapshot: BrokerSnapshot | None = None,
    ) -> dict[str, Any]:
        preferred_path = (
            selected_path
            if self._runtime.active_broker.id == previous_active_id
            else ""
        )
        snapshot = self._snapshot(preferred_path, broker_snapshot)
        active_id = UUID(snapshot["active_broker_id"])
        return {
            "snapshot": snapshot,
            "selection": snapshot["initial_selection"],
            "broker_control": self._broker_control(active_id),
        }

    @staticmethod
    def _status_value(status: object) -> str:
        return str(getattr(status, "value", status)).lower()

    def _build_dashboard(self, **tools: Any) -> PrefabApp:
        snapshot = self._snapshot()
        broker_control = self._broker_control(
            UUID(snapshot["active_broker_id"])
        )

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
                    "min-h-[calc(100vh-7.5rem)] border-t border-[#c8ced6]"
                ),
            ):
                self._build_tree(tools)
                self._build_details()

        return PrefabApp(
            title="TopicGate Control Dashboard",
            view=view,
            mode="light",
            on_mount=RequestDisplayMode("fullscreen"),
            state={
                "snapshot": snapshot,
                "selection": snapshot["initial_selection"],
                "broker_control": broker_control,
            },
        )

    def _build_header(self, snapshot: dict[str, Any], tools: dict[str, Any]) -> None:
        with Grid(
            columns=None,
            gap=5,
            css_class=(
                "min-h-[7.5rem] grid-cols-1 items-center bg-[#ffffff] "
                "px-6 py-5 lg:grid-cols-[minmax(12rem,1fr)_minmax(34rem,auto)] "
                "lg:px-8"
            ),
        ):
            with Column(gap=1):
                Heading(
                    "TopicGate",
                    level=1,
                    css_class="text-2xl font-semibold tracking-[-0.035em]",
                )
                Text(
                    "MQTT control dashboard",
                    css_class="text-sm text-[#5f6368]",
                )
            with Column(gap=2, css_class="min-w-0 lg:min-w-[34rem]"):
                Label(
                    "BROKER",
                    css_class="text-xs font-semibold text-[#4b5563]",
                )
                with Row(gap=2, align="center", css_class="flex-wrap lg:flex-nowrap"):
                    with Select(
                        name="dashboard_broker_id",
                        value=f"{STATE.broker_control.selected_broker_id}",
                        on_change=CallTool(
                            tools["select_broker"],
                            arguments={"broker_id": EVENT},
                            on_success=SetState("broker_control", RESULT),
                            on_error=ShowToast(
                                "Could not select broker",
                                variant="error",
                            ),
                        ),
                        css_class=(
                            "h-10 min-w-56 flex-1 border-[#b8c0ca] "
                            "bg-[#ffffff] text-sm text-[#202124]"
                        ),
                    ):
                        for broker in snapshot["brokers"]:
                            SelectOption(
                                broker["name"],
                                value=broker["id"],
                                selected=(
                                    broker["id"] == snapshot["active_broker_id"]
                                ),
                            )
                    self._broker_action_button(
                        "Connect",
                        tools["connect_broker"],
                        STATE.broker_control.connect_disabled,
                        "Could not connect broker",
                    )
                    self._broker_action_button(
                        "Reconnect & observe",
                        tools["reconnect_observe_broker"],
                        STATE.broker_control.reconnect_observe_disabled,
                        "Could not reconnect and observe broker",
                    )
                    self._broker_action_button(
                        "Disconnect",
                        tools["disconnect_broker"],
                        STATE.broker_control.disconnect_disabled,
                        "Could not disconnect broker",
                    )
                with Row(gap=2, align="center", css_class="min-w-0 flex-wrap"):
                    Text(
                        f"{STATE.broker_control.endpoint}",
                        code=True,
                        css_class=(
                            "min-w-0 select-text break-all text-xs "
                            "text-[#5f6368]"
                        ),
                    )
                    self._build_connection_status()

    @staticmethod
    def _broker_action_button(
        label: str,
        tool: Any,
        disabled: Any,
        error_message: str,
    ) -> None:
        Button(
            label,
            variant="outline",
            size="sm",
            disabled=disabled,
            on_click=CallTool(
                tool,
                arguments={
                    "broker_id": STATE.broker_control.selected_broker_id,
                    "selected_path": STATE.selection.path,
                },
                on_success=[
                    SetState("snapshot", RESULT.snapshot),
                    SetState("selection", RESULT.selection),
                    SetState("broker_control", RESULT.broker_control),
                ],
                on_error=ShowToast(error_message, variant="error"),
            ),
            css_class="h-10 whitespace-nowrap border-[#b8c0ca] bg-white",
        )

    @staticmethod
    def _build_connection_status() -> None:
        with Row(gap=2, align="center", css_class="whitespace-nowrap"):
            with If("broker_control.connection_status == 'connected'"):
                Div(css_class="size-2 rounded-full bg-[#168a55]")
            with If(
                "broker_control.connection_status == 'connecting' || "
                "broker_control.connection_status == 'reconnecting'"
            ):
                Div(css_class="size-2 rounded-full bg-[#b66a00]")
            with If("broker_control.connection_status == 'disconnected'"):
                Div(css_class="size-2 rounded-full bg-[#c43d3d]")
            Text(
                f"{STATE.broker_control.connection_status_label}",
                css_class="text-xs text-[#4b5563]",
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
        with Div(css_class="relative"):
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
                    "pr-7 font-mono text-[13px] font-normal "
                    "hover:border-l-[#9aa8b6] hover:bg-[#eef2f6] "
                    f"hover:text-[#202124] {selected_class}"
                ),
            )
            with If(item.status == "live"):
                Div(
                    css_class=(
                        "absolute right-2 top-[0.875rem] size-2 "
                        "rounded-full bg-[#16a34a]"
                    )
                )
            with If(item.status == "cached"):
                Div(
                    css_class=(
                        "absolute right-2 top-[0.875rem] size-2 "
                        "rounded-full bg-[#3b82f6]"
                    )
                )
            with If(item.status == "stale"):
                Div(
                    css_class=(
                        "absolute right-2 top-[0.875rem] size-2 "
                        "rounded-full bg-[#d97706]"
                    )
                )

    def _build_details(self) -> None:
        with Column(
            gap=6,
            css_class=(
                "min-w-0 max-w-6xl px-6 py-8 lg:px-10 lg:py-10 xl:px-12"
            ),
        ):
            with Column(gap=3):
                Heading(
                    "Details / Stats",
                    level=2,
                    css_class="text-lg font-medium tracking-tight",
                )
                with Div(
                    css_class=(
                        "rounded-md border border-[#c8ced6] bg-white px-5 py-4"
                    )
                ):
                    self._build_topic_status()
                    with Column(gap=2, css_class="mt-4"):
                        self._detail_row(
                            "Topic path",
                            STATE.selection.topic.topic,
                            code=True,
                        )
                        self._detail_row(
                            "Last received",
                            STATE.selection.topic.received_at,
                        )
                        self._detail_row("Age", STATE.selection.topic.age_label)
                        self._detail_row(
                            "Observation source",
                            STATE.selection.topic.source_label,
                        )
                        self._detail_row(
                            "State",
                            STATE.selection.topic.status_label,
                        )
                        self._detail_row(
                            "Encoding",
                            STATE.selection.topic.payload_encoding,
                        )
                        self._detail_row(
                            "Payload size",
                            STATE.selection.topic.payload_size_label,
                        )
                        self._detail_row(
                            "Original payload",
                            STATE.selection.topic.original_payload_size_label,
                        )
                        self._detail_row(
                            "Available payload",
                            STATE.selection.topic.available_payload_size_label,
                        )
                        self._detail_row(
                            "Rendered payload",
                            f"{STATE.selection.topic.rendered_payload_size} bytes",
                        )
                        self._detail_row(
                            "Ingestion truncation",
                            STATE.selection.topic.ingestion_truncation_label,
                        )
                        self._detail_row(
                            "Rendering truncation",
                            STATE.selection.topic.rendering_truncation_label,
                        )
                        self._detail_row("QoS", STATE.selection.topic.qos_label)
                        self._detail_row(
                            "Retained",
                            STATE.selection.topic.retain_label,
                        )
                        self._detail_row(
                            "Message count",
                            STATE.selection.topic.message_count,
                        )
                        self._detail_row(
                            "Dropped messages",
                            STATE.selection.topic.dropped_message_count,
                        )

            with Column(gap=2):
                Heading(
                    "Decoded payload",
                    level=2,
                    css_class="text-sm font-medium text-[#202124]",
                )
                with Div(
                    css_class=(
                        "min-h-36 rounded-md border border-[#c8ced6] "
                        "bg-[#fbfcfd] px-4 py-3"
                    )
                ):
                    Text(
                        f"{STATE.selection.topic.decoded_payload}",
                        code=True,
                        css_class=(
                            "max-h-80 select-text overflow-auto whitespace-pre-wrap "
                            "break-words text-sm leading-6 text-[#202124]"
                        ),
                    )

            with Column(gap=2):
                Heading(
                    "Raw payload (hex)",
                    level=2,
                    css_class="text-sm font-medium text-[#202124]",
                )
                with Div(
                    css_class=(
                        "min-h-20 rounded-md border border-[#c8ced6] "
                        "bg-[#fbfcfd] px-4 py-3"
                    )
                ):
                    Text(
                        f"{STATE.selection.topic.raw_payload}",
                        code=True,
                        css_class=(
                            "max-h-48 select-text overflow-auto whitespace-pre-wrap "
                            "break-words text-xs leading-5 text-[#4b5563]"
                        ),
                    )

            self._build_snapshot_health()
            self._build_subscription_settings()

    @staticmethod
    def _build_topic_status() -> None:
        with Row(gap=2, align="center", css_class="flex-wrap"):
            with If("selection.topic.status == 'live'"):
                with Row(
                    gap=2,
                    align="center",
                    css_class="rounded-full bg-[#dcfce7] px-3 py-1 text-sm text-[#166534]",
                ):
                    Div(css_class="size-2 rounded-full bg-[#16a34a]")
                    Text("Live")
            with If("selection.topic.status == 'cached'"):
                with Row(
                    gap=2,
                    align="center",
                    css_class="rounded-full bg-[#dbeafe] px-3 py-1 text-sm text-[#1d4ed8]",
                ):
                    Div(css_class="size-2 rounded-full bg-[#3b82f6]")
                    Text("Cached")
            with If("selection.topic.status == 'stale'"):
                with Row(
                    gap=2,
                    align="center",
                    css_class="rounded-full bg-[#fef3c7] px-3 py-1 text-sm text-[#92400e]",
                ):
                    Div(css_class="size-2 rounded-full bg-[#d97706]")
                    Text("Stale")
            with If("selection.topic.status == 'waiting'"):
                with Row(
                    gap=2,
                    align="center",
                    css_class=(
                        "rounded-full bg-[#eef1f4] px-3 py-1 "
                        "text-sm text-[#4b5563]"
                    ),
                ):
                    Div(css_class="size-2 rounded-full bg-[#9aa0a6]")
                    Text("Waiting")
            with If("selection.topic.source == 'stored'"):
                Text(
                    "Persisted origin",
                    css_class=(
                        "rounded-full border border-[#c8ced6] px-3 py-1 "
                        "text-sm text-[#4b5563]"
                    ),
                )
            with If("selection.topic.retained"):
                Text(
                    "Retained",
                    css_class="rounded-full border border-[#c8ced6] px-3 py-1 text-sm text-[#4b5563]",
                )
        Text(
            f"{STATE.selection.topic.status_detail}",
            css_class="mt-2 text-sm text-[#5f6368]",
        )

    def _build_snapshot_health(self) -> None:
        with Column(gap=3):
            Heading(
                "Snapshot",
                level=2,
                css_class="text-lg font-medium tracking-tight",
            )
            with Div(
                css_class="rounded-md border border-[#c8ced6] bg-white px-5 py-4"
            ):
                with Column(gap=2):
                    self._detail_row("Captured", STATE.snapshot.captured_at_label)
                    self._detail_row(
                        "Observation started",
                        STATE.snapshot.observation_started_at_label,
                    )
                    self._detail_row(
                        "Observed for",
                        STATE.snapshot.observed_for_label,
                    )
                    self._detail_row(
                        "Dropped messages",
                        STATE.snapshot.dropped_message_count,
                    )
                    self._detail_row(
                        "Completeness",
                        STATE.snapshot.completeness.status_label,
                    )
                    self._detail_row(
                        "Results",
                        f"{STATE.snapshot.results.returned} returned of "
                        f"{STATE.snapshot.results.total}",
                    )
                    self._detail_row(
                        "Omitted",
                        STATE.snapshot.results.omitted,
                    )
                with If("snapshot.completeness.limitations_labels.length > 0"):
                    with Div(
                        css_class=(
                            "mt-4 border-l-2 border-[#d97706] bg-[#fffbeb] "
                            "px-4 py-3"
                        )
                    ):
                        Text(
                            "Completeness limitations",
                            css_class="mb-1 text-sm font-medium text-[#78350f]",
                        )
                        with Column(gap=1):
                            with ForEach(
                                "snapshot.completeness.limitations_labels"
                            ) as limitation:
                                Text(
                                    f"{limitation}",
                                    css_class="text-sm leading-5 text-[#78350f]",
                                )

    def _build_subscription_settings(self) -> None:
        with Column(gap=3):
            Heading(
                "Subscription",
                level=2,
                css_class="text-lg font-medium tracking-tight",
            )
            with Div(
                css_class="rounded-md border border-[#c8ced6] bg-white px-5 py-4"
            ):
                with Column(gap=2):
                    self._detail_row(
                        "Matching filter",
                        STATE.selection.subscription.topic_filter,
                        code=True,
                    )
                    self._detail_row("QoS", STATE.selection.subscription.qos_label)
                    self._detail_row(
                        "Retention",
                        STATE.selection.subscription.retain_as_published_label,
                    )
                    self._detail_row(
                        "Retained-message handling",
                        STATE.selection.subscription.retain_handling_label,
                    )

    @staticmethod
    def _detail_row(label: str, value: Any, *, code: bool = False) -> None:
        with Grid(
            columns=2,
            gap=3,
            css_class="grid-cols-[10rem_minmax(0,1fr)] text-sm",
        ):
            Text(label, css_class="text-[#5f6368]")
            Text(
                f"{value}",
                code=code,
                css_class="min-w-0 select-text break-words text-[#202124]/85",
            )

    def _selection(self, broker_id: UUID, path: str) -> dict[str, Any]:
        return self._snapshot_builder.selection(broker_id, path)
