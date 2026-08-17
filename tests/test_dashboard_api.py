import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastmcp import Client, FastMCP

from topicgate.app.models.broker_snapshot import SnapshotLimitation
from topicgate.app.services.broker_snapshot_service import BrokerSnapshotService
from topicgate.core.models.connection_status import ConnectionStatus
from topicgate.core.models.mqtt_observation import ObservationSource
from topicgate.core.models.observer_model import ObserverModel, TopicState
from topicgate.core.models.subscription import Subscription
from topicgate.mcp.api.dashboard_api import DashboardAPI


def dashboard_runtime() -> MagicMock:
    runtime = MagicMock()
    broker = SimpleNamespace(
        id=uuid4(),
        name="Local",
        config=SimpleNamespace(host="127.0.0.1", port=1883, use_tls=False),
    )
    runtime.active_broker = broker
    runtime.connection_status = ConnectionStatus.CONNECTED
    runtime.dropped_message_count = 3
    runtime.list_brokers.return_value = (broker,)
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
    runtime.get_observer_model.return_value = ObserverModel(
        root_stats=[],
        topic_states={
            topic_state.topic: topic_state,
            unrelated_state.topic: unrelated_state,
        },
    )
    runtime.get_connection_status.return_value = ConnectionStatus.CONNECTED
    runtime.get_dropped_message_count.return_value = 3
    runtime.get_connected_at.return_value = None
    runtime.get_observation_started_at.return_value = None
    runtime.activate_broker = AsyncMock()
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
        "activate_dashboard_broker",
        "open_topicgate_dashboard",
        "select_dashboard_path",
    }
    for item in tools:
        assert item.description is not None
        assert "Side effects:" in item.description
        assert "Required state:" in item.description
        assert "Identifiers:" in item.description
        assert "Failures:" in item.description


def test_dashboard_renders_monitoring_only_two_column_workspace() -> None:
    api = DashboardAPI(dashboard_runtime())

    rendered = json.dumps(api.open_topicgate_dashboard().to_json())

    assert "Subscriptions" in rendered
    assert "Metadata" in rendered
    assert "Subscription" in rendered
    assert "Source" in rendered
    assert "Truncation" in rendered
    assert "Connected" in rendered
    assert "border-[#c8ced6]" in rendered
    assert "border-[#b8c0ca]" in rendered
    assert "bg-[#dce9f7]" in rendered
    assert "border-l-[#405d7a]" in rendered
    assert "bg-[#fbfcfd]" in rendered
    for removed_label in (
        "Observer Tree",
        "Details / Stats",
        "Add subscription",
        "Remove subscription",
        "Connect",
        "Reconnect",
        "Disconnect",
        "Refresh",
        "Publish message",
        "Apply",
        "Revert",
    ):
        assert f'"label": "{removed_label}"' not in rendered


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


def test_dashboard_uses_shared_truncation_freshness_and_provenance() -> None:
    runtime = dashboard_runtime()
    state = runtime.get_observer_model.return_value.topic_states[
        "sensors/kitchen/temperature"
    ]
    state.payload_size = 20
    state.source = ObservationSource.STORED
    captured_at = state.received_at.replace(minute=31)
    api = DashboardAPI(
        runtime,
        BrokerSnapshotService(runtime, clock=lambda: captured_at),
    )

    snapshot = api._snapshot()
    selected = snapshot["initial_selection"]["topic"]

    assert selected["age_seconds"] == 60
    assert selected["source"] == "stored"
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


def test_empty_broker_has_an_empty_tree_and_selection() -> None:
    runtime = dashboard_runtime()
    runtime.list_subscriptions.return_value = ()
    runtime.get_observer_model.return_value = ObserverModel(
        root_stats=[],
        topic_states={},
    )
    api = DashboardAPI(runtime)

    snapshot = api._snapshot()

    assert snapshot["tree_rows"] == []
    assert snapshot["initial_selection"]["path"] == "No topic selected"
    assert snapshot["initial_selection"]["subscription"]["topic_filter"] == (
        "No matching subscription"
    )
