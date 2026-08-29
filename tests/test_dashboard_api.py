import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastmcp import Client, FastMCP

from topicgate.app.models.broker_snapshot import SnapshotLimitation
from topicgate.app.services.broker_snapshot_service import BrokerSnapshotService
from topicgate.core.models.connection_status import ConnectionStatus
from topicgate.core.models.current_topic import CurrentTopic
from topicgate.core.models.mqtt_observation import MqttObservation as TopicState
from topicgate.core.models.mqtt_observation import ObservationSource
from topicgate.core.models.observation_status import ObservationStatus
from topicgate.core.models.subscription import Subscription
from topicgate.core.models.topic_message import TopicMessage
from topicgate.mcp.api.dashboard_api import DashboardAPI


def dashboard_runtime() -> MagicMock:
    runtime = MagicMock()
    broker = SimpleNamespace(
        id=uuid4(),
        name="Local",
        config=SimpleNamespace(host="127.0.0.1", port=1883, use_tls=False),
    )
    inactive_broker = SimpleNamespace(
        id=uuid4(),
        name="Remote",
        config=SimpleNamespace(host="remote.local", port=8883, use_tls=True),
    )
    runtime.active_broker = broker
    runtime.connection_status = ConnectionStatus.CONNECTED
    runtime.dropped_message_count = 3
    runtime.list_brokers.return_value = (broker, inactive_broker)
    runtime.get_broker.side_effect = lambda broker_id: next(
        item for item in (broker, inactive_broker) if item.id == broker_id
    )
    runtime.list_subscriptions.return_value = (
        Subscription("sensors/#", qos=0, retain_handling=2),
        Subscription("sensors/+/temperature", qos=1),
    )
    topic_state = TopicState(
        "temperature",
        "sensors/kitchen/temperature",
        b"22.4",
        1,
        False,
        datetime(2026, 8, 11, 10, 30, tzinfo=timezone.utc),
    )
    unrelated_state = TopicState(
        "topic",
        "unrelated/topic",
        b"ignored",
        0,
        False,
        datetime(2026, 8, 11, 10, 29, tzinfo=timezone.utc),
    )
    topic_states = (topic_state, unrelated_state)
    runtime.test_topic_state = topic_state
    runtime.get_current_topics.side_effect = lambda _broker_id: tuple(
        CurrentTopic(
            TopicMessage(
                broker_id=broker.id,
                topic=state.topic,
                payload=state.payload,
                qos=state.qos,
                retain=state.retain,
                received_at=state.received_at,
                payload_size=state.payload_size or len(state.payload),
                message_count=state.message_count,
                observation_id=uuid4(),
            ),
            (
                ObservationStatus.CACHED
                if state.source is ObservationSource.STORED
                else ObservationStatus.LIVE
            ),
        )
        for state in topic_states
    )
    runtime.get_connection_status.side_effect = lambda broker_id: (
        ConnectionStatus.CONNECTED
        if broker_id == broker.id
        else ConnectionStatus.DISCONNECTED
    )
    runtime.get_dropped_message_count.return_value = 3
    runtime.get_connected_at.return_value = None
    runtime.get_observation_started_at.return_value = None
    runtime.activate_broker = AsyncMock()
    runtime.connect = AsyncMock()
    runtime.disconnect = AsyncMock()
    return runtime


async def test_dashboard_registers_only_its_entry_point_for_the_model() -> None:
    async def scenario() -> None:
        mcp = FastMCP("test")
        DashboardAPI(dashboard_runtime()).register(mcp, control_enabled=True)

        async with Client(mcp) as client:
            tools = await client.list_tools()

        assert [item.name for item in tools] == ["open_topicgate_dashboard"]
        description = tools[0].description
        assert description is not None
        assert "control-mode" in description
        assert "unavailable in read-only mode" in description
        assert "Side effects:" in description
        assert "Required state:" in description
        assert "Identifiers:" in description
        assert "Failures:" in description

    await scenario()


async def test_read_only_mode_omits_dashboard_broker_activation_surface() -> None:
    mcp = FastMCP("test")
    DashboardAPI(dashboard_runtime()).register(mcp, control_enabled=False)

    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert tools == []


async def test_dashboard_provider_tools_describe_operational_contracts() -> None:
    api = DashboardAPI(dashboard_runtime())

    tools = await api._app.list_tools()

    assert {item.name for item in tools} == {
        "connect_dashboard_broker",
        "disconnect_dashboard_broker",
        "open_topicgate_dashboard",
        "reconnect_observe_dashboard_broker",
        "select_dashboard_broker",
        "select_dashboard_path",
    }
    for item in tools:
        assert item.description is not None
        assert "Side effects:" in item.description
        assert "Required state:" in item.description
        assert "Identifiers:" in item.description
        assert "Failures:" in item.description


def test_dashboard_renders_light_broker_controls_and_vertical_details() -> None:
    api = DashboardAPI(dashboard_runtime())

    rendered = json.dumps(api.open_topicgate_dashboard().to_json())

    assert "Subscriptions" in rendered
    assert "Details / Stats" in rendered
    assert "Subscription" in rendered
    assert "Observation source" in rendered
    assert "Ingestion truncation" in rendered
    assert "Rendering truncation" in rendered
    assert "Observation started" in rendered
    assert "Snapshot" in rendered
    assert "Completeness limitations" in rendered
    assert "Persisted origin" in rendered
    assert "Retained" in rendered
    assert "Live" in rendered
    assert "Cached" in rendered
    assert "Stale" in rendered
    assert "Connected" in rendered
    assert "Connect" in rendered
    assert "Reconnect & observe" in rendered
    assert "Disconnect" in rendered
    assert "Decoded payload" in rendered
    assert "Raw payload (hex)" in rendered
    assert "dashboard_broker_id" in rendered
    assert "border-[#c8ced6]" in rendered
    assert "border-[#b8c0ca]" in rendered
    assert "bg-[#dce9f7]" in rendered
    assert "border-l-[#405d7a]" in rendered
    assert "bg-[#fbfcfd]" in rendered
    assert "Control action" not in rendered
    assert "Switching disconnects the current broker" not in rendered
    assert "border-[#f3d18a]" not in rendered
    assert "text-3xl" not in rendered
    assert "lg:text-5xl" not in rendered
    for removed_label in (
        "Observer Tree",
        "Add subscription",
        "Remove subscription",
        "Refresh",
        "Publish message",
        "Apply",
        "Revert",
    ):
        assert f'"label": "{removed_label}"' not in rendered


def test_broker_selector_is_passive_and_presents_selected_profile() -> None:
    runtime = dashboard_runtime()
    inactive = runtime.list_brokers.return_value[1]
    api = DashboardAPI(runtime)

    control = api._select_dashboard_broker(str(inactive.id))

    runtime.activate_broker.assert_not_awaited()
    runtime.connect.assert_not_awaited()
    runtime.disconnect.assert_not_awaited()
    assert control["selected_broker_id"] == str(inactive.id)
    assert control["endpoint"] == "mqtts://remote.local:8883"
    assert control["can_connect"] is True
    assert control["can_disconnect"] is False


async def test_connect_targets_the_selected_profile_and_refreshes_state() -> None:
    runtime = dashboard_runtime()
    inactive = runtime.list_brokers.return_value[1]
    api = DashboardAPI(runtime)

    state = await api._connect_dashboard_broker(
        str(inactive.id),
        "sensors/kitchen/temperature",
    )

    runtime.activate_broker.assert_awaited_once_with(inactive.id)
    runtime.connect.assert_not_awaited()
    assert set(state) == {"snapshot", "selection", "broker_control"}


async def test_connect_uses_runtime_connect_for_active_disconnected_profile() -> None:
    runtime = dashboard_runtime()
    active = runtime.active_broker
    runtime.get_connection_status.side_effect = lambda _broker_id: (
        ConnectionStatus.DISCONNECTED
    )
    api = DashboardAPI(runtime)

    await api._connect_dashboard_broker(str(active.id))

    runtime.activate_broker.assert_not_awaited()
    runtime.connect.assert_awaited_once_with()


async def test_disconnect_only_targets_the_active_selected_profile() -> None:
    runtime = dashboard_runtime()
    active, inactive = runtime.list_brokers.return_value
    api = DashboardAPI(runtime)

    await api._disconnect_dashboard_broker(str(active.id))
    runtime.disconnect.assert_awaited_once_with()

    try:
        await api._disconnect_dashboard_broker(str(inactive.id))
    except ValueError as error:
        assert "active connected broker" in str(error)
    else:
        raise AssertionError("Inactive broker disconnect should fail")
    assert runtime.disconnect.await_count == 1


async def test_reconnect_observe_uses_default_wait_and_preserves_selection() -> None:
    runtime = dashboard_runtime()
    active = runtime.active_broker
    api = DashboardAPI(runtime)
    observed_snapshot = api._snapshot_service.build_current(active.id)
    api._snapshot_service.observe = AsyncMock(return_value=observed_snapshot)

    state = await api._reconnect_observe_dashboard_broker(
        str(active.id),
        "sensors/kitchen/temperature",
    )

    api._snapshot_service.observe.assert_awaited_once_with(active.id)
    assert state["selection"]["path"] == "sensors/kitchen/temperature"


def test_snapshot_falls_back_when_preferred_path_is_not_selectable() -> None:
    api = DashboardAPI(dashboard_runtime())

    snapshot = api._snapshot("unrelated/topic")

    assert snapshot["initial_selection"]["path"] == (
        "sensors/kitchen/temperature"
    )


def test_dashboard_serializes_reactive_action_states_and_failure_toasts() -> None:
    rendered = json.dumps(
        DashboardAPI(dashboard_runtime()).open_topicgate_dashboard().to_json()
    )

    assert "broker_control.connect_disabled" in rendered
    assert "broker_control.reconnect_observe_disabled" in rendered
    assert "broker_control.disconnect_disabled" in rendered
    assert "Could not connect broker" in rendered
    assert "Could not disconnect broker" in rendered
    assert "Could not reconnect and observe broker" in rendered


def test_snapshot_merges_filters_and_matching_topics_into_tree() -> None:
    api = DashboardAPI(dashboard_runtime())

    snapshot = api._snapshot()

    paths = [row["path"] for row in snapshot["tree_rows"]]
    assert paths == [
        "sensors",
        "sensors/#",
        "sensors/+",
        "sensors/+/temperature",
        "sensors/kitchen",
        "sensors/kitchen/temperature",
    ]
    assert "unrelated/topic" not in paths
    assert snapshot["initial_selection"]["path"] == (
        "sensors/kitchen/temperature"
    )
    assert snapshot["initial_selection"]["topic"]["payload_display"] == "22.4"
    assert next(
        row
        for row in snapshot["tree_rows"]
        if row["path"] == "sensors/kitchen/temperature"
    )["status"] == "live"


def test_selection_uses_the_most_specific_matching_subscription() -> None:
    runtime = dashboard_runtime()
    api = DashboardAPI(runtime)

    selection = api._select_dashboard_path("sensors/kitchen/temperature")

    assert selection["subscription"]["topic_filter"] == (
        "sensors/+/temperature"
    )
    assert selection["subscription"]["qos_label"] == "1 · At least once"
    assert selection["topic"]["dropped_message_count"] == 3


def test_selecting_filter_without_state_shows_settings_and_empty_value() -> None:
    api = DashboardAPI(dashboard_runtime())

    selection = api._select_dashboard_path("sensors/#")

    assert selection["topic"]["payload_display"] == "No value observed"
    assert selection["subscription"]["topic_filter"] == "sensors/#"
    assert selection["subscription"]["retain_handling_label"] == (
        "Do not send retained messages"
    )


def test_snapshot_keeps_payload_representations_for_selected_topic() -> None:
    api = DashboardAPI(dashboard_runtime())

    selected = api._snapshot()["initial_selection"]["topic"]

    assert selected["payload_text"] == "22.4"
    assert selected["payload_base64"] == "MjIuNA=="
    assert selected["payload_encoding"] == "UTF-8"
    assert {
        "topic",
        "received_at",
        "age_label",
        "source_label",
        "status_label",
        "payload_encoding",
        "payload_size_label",
        "original_payload_size_label",
        "available_payload_size_label",
        "rendered_payload_size",
        "ingestion_truncation_label",
        "rendering_truncation_label",
        "qos_label",
        "retain_label",
        "message_count",
        "dropped_message_count",
        "decoded_payload",
        "raw_payload",
    } <= selected.keys()


def test_dashboard_uses_shared_truncation_freshness_and_provenance() -> None:
    runtime = dashboard_runtime()
    state = runtime.test_topic_state
    state.payload_size = 20
    state.source = ObservationSource.STORED
    captured_at = state.received_at.replace(minute=31)
    runtime.get_observation_started_at.return_value = (
        state.received_at + timedelta(seconds=30)
    )
    api = DashboardAPI(
        runtime,
        BrokerSnapshotService(runtime, clock=lambda: captured_at),
    )

    snapshot = api._snapshot()
    selected = snapshot["initial_selection"]["topic"]

    assert selected["age_seconds"] == 60
    assert selected["source"] == "stored"
    assert selected["source_label"] == "Persisted storage"
    assert selected["status"] == "stale"
    assert selected["status_label"] == "Stale"
    assert selected["retain_label"] == "No"
    assert selected["is_truncated"] is True
    assert selected["ingestion_truncated"] is True
    assert SnapshotLimitation.PAYLOAD_TRUNCATED in (
        snapshot["completeness"]["limitations"]
    )
    assert SnapshotLimitation.STORED_STATE_PREDATES_OBSERVATION in (
        snapshot["completeness"]["limitations"]
    )
    assert snapshot["freshness"] == {
        "max_age_seconds": None,
        "stale_count": 0,
    }
    assert snapshot["observation_started_at_label"] == (
        "2026-08-11T10:30:30+00:00"
    )
    assert snapshot["observed_for_label"] == "30.0 seconds"
    assert snapshot["dropped_message_count"] == 3
    assert snapshot["completeness"]["status_label"] == "Limited"
    assert "Persisted values may predate the current observation window." in (
        snapshot["completeness"]["limitations_labels"]
    )


def test_empty_broker_has_an_empty_tree_and_selection() -> None:
    runtime = dashboard_runtime()
    runtime.list_subscriptions.return_value = ()
    runtime.get_current_topics.side_effect = lambda _broker_id: ()
    api = DashboardAPI(runtime)

    snapshot = api._snapshot()

    assert snapshot["tree_rows"] == []
    assert snapshot["initial_selection"]["path"] == "No topic selected"
    assert snapshot["initial_selection"]["subscription"]["topic_filter"] == (
        "No matching subscription"
    )
