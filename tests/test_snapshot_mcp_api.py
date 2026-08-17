from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastmcp import Client, FastMCP

from topicgate.app.models.broker_snapshot import (
    BrokerSnapshot,
    SnapshotBrokerIdentity,
    SnapshotCompleteness,
    SnapshotFreshness,
    SnapshotLimitation,
    SnapshotResultLimit,
    SnapshotSettling,
)
from topicgate.mcp.api.snapshot_api import SnapshotAPI


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


def broker_snapshot() -> BrokerSnapshot:
    return BrokerSnapshot(
        broker=SnapshotBrokerIdentity(uuid4(), "Primary"),
        connection_status="disconnected",
        captured_at=NOW,
        connected_at=None,
        observation_started_at=None,
        observed_for_seconds=None,
        topic_filter="#",
        topics=(),
        dropped_message_count=0,
        freshness=SnapshotFreshness(None, 0),
        results=SnapshotResultLimit(100, 0, 0, 0, 0, 0, False),
        settling=SnapshotSettling(0, 5, 0),
        completeness=SnapshotCompleteness(
            False,
            (SnapshotLimitation.CURRENT_STATE_ONLY,),
        ),
    )


async def test_snapshot_api_maps_public_arguments_to_service() -> None:
    service = MagicMock()
    service.build = AsyncMock(return_value=broker_snapshot())
    service.observe = AsyncMock(return_value=broker_snapshot())
    api = SnapshotAPI(service)

    await api.get_broker_snapshot(
        "Primary",
        topic_filter="home/#",
        max_age_seconds=30,
        limit=10,
        payload_limit_bytes=512,
    )
    await api.observe_broker_snapshot(
        "Primary",
        topic_filter="home/#",
        max_age_seconds=30,
        limit=10,
        payload_limit_bytes=512,
        wait_seconds=2,
    )

    service.build.assert_awaited_once_with(
        "Primary",
        topic_filter="home/#",
        max_age_seconds=30,
        result_limit=10,
        payload_limit_bytes=512,
    )
    service.observe.assert_awaited_once_with(
        "Primary",
        topic_filter="home/#",
        max_age_seconds=30,
        result_limit=10,
        payload_limit_bytes=512,
        wait_seconds=2,
    )


async def test_snapshot_tools_register_with_side_effect_annotations() -> None:
    service = MagicMock()
    service.build = AsyncMock(return_value=broker_snapshot())
    service.observe = AsyncMock(return_value=broker_snapshot())
    mcp = FastMCP("test")
    SnapshotAPI(service).register(mcp, control_enabled=True)

    async with Client(mcp) as client:
        tools = {item.name: item for item in await client.list_tools()}
        result = await client.call_tool(
            "get_broker_snapshot",
            {"broker": "Primary"},
        )

    assert set(tools) == {"get_broker_snapshot", "observe_broker_snapshot"}
    assert tools["get_broker_snapshot"].annotations.readOnlyHint is True
    assert tools["observe_broker_snapshot"].annotations.readOnlyHint is False
    for item in tools.values():
        assert item.description is not None
        assert "Side effects:" in item.description
        assert "Required state:" in item.description
        assert "Identifiers:" in item.description
        assert "Failures:" in item.description
    assert result.data.broker.name == "Primary"
    assert result.data.completeness.limitations == ["current_state_only"]


async def test_read_only_snapshot_api_omits_observation_refresh() -> None:
    mcp = FastMCP("test")
    SnapshotAPI(MagicMock()).register(mcp, control_enabled=False)

    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert [item.name for item in tools] == ["get_broker_snapshot"]
