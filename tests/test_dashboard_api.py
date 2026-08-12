import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastmcp import Client, FastMCP

from topicgate.core.models.connection_status import ConnectionStatus
from topicgate.core.models.observer_model import TopicState
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
    runtime.list_topics.return_value = (
        "sensors/kitchen/temperature",
        "unrelated/topic",
    )
    runtime.get_topic_state.side_effect = lambda _broker_id, topic: (
        TopicState(
            "temperature",
            "sensors/kitchen/temperature",
            b"22.4",
            1,
            False,
            datetime(2026, 8, 11, 10, 30, tzinfo=timezone.utc),
        )
        if topic == "sensors/kitchen/temperature"
        else None
    )
    runtime.activate_broker = AsyncMock()
    return runtime


async def test_dashboard_registers_only_its_entry_point_for_the_model() -> None:
    async def scenario() -> None:
        mcp = FastMCP("test")
        DashboardAPI(dashboard_runtime()).register(mcp)

        async with Client(mcp) as client:
            tools = await client.list_tools()

        assert [item.name for item in tools] == ["open_topicgate_dashboard"]

    await scenario()


def test_dashboard_renders_monitoring_only_two_column_workspace() -> None:
    api = DashboardAPI(dashboard_runtime())

    rendered = json.dumps(api.open_topicgate_dashboard().to_json())

    assert "Subscriptions" in rendered
    assert "Metadata" in rendered
    assert "Subscription" in rendered
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


def test_empty_broker_has_an_empty_tree_and_selection() -> None:
    runtime = dashboard_runtime()
    runtime.list_subscriptions.return_value = ()
    runtime.list_topics.return_value = ()
    api = DashboardAPI(runtime)

    snapshot = api._snapshot()

    assert snapshot["tree_rows"] == []
    assert snapshot["initial_selection"]["path"] == "No topic selected"
    assert snapshot["initial_selection"]["subscription"]["topic_filter"] == (
        "No matching subscription"
    )
