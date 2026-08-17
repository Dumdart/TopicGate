import socket
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from topicgate.app.app_dependencies import AppDependencies
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.topic_message import TopicMessage
from topicgate.mcp.server import Server


def unavailable_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def seed_disconnected_broker(
    data_dir: Path,
    credential_store,
    port: int,
) -> str:
    dependencies = AppDependencies(data_dir, credential_store)
    profile = dependencies.broker_profiles.get_profile()
    profile.name = "Cached Plant"
    profile.config = MqttConfig("127.0.0.1", port, "", "")
    dependencies.broker_profiles.update_profile(profile)
    observation_id = uuid4()
    dependencies.topic_messages.update_message(
        TopicMessage(
            broker_id=profile.id,
            topic="plant/temperature",
            payload=b"21.5",
            qos=1,
            retain=True,
            received_at=datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc),
            payload_size=4,
            message_count=7,
            observation_id=observation_id,
        )
    )
    dependencies.topic_messages.close()
    dependencies._db_context.dispose()
    return str(profile.id)


async def test_unreachable_broker_startup_keeps_mcp_reads_and_reconnect_usable(
    tmp_path: Path,
    credential_store,
) -> None:
    port = unavailable_local_port()
    broker_id = seed_disconnected_broker(
        tmp_path,
        credential_store,
        port,
    )
    dependencies = AppDependencies(tmp_path, credential_store)

    with patch(
        "topicgate.mcp.server.AppDependencies",
        return_value=dependencies,
    ):
        server = Server()

    async with Client(server.mcp) as client:
        brokers = await client.call_tool("list_brokers", {})
        snapshot = await client.call_tool(
            "get_broker_snapshot",
            {"broker": "Cached Plant"},
        )
        status = await client.call_tool(
            "get_connection_status",
            {"broker": broker_id},
        )

        with pytest.raises(ToolError, match="The MQTT broker operation failed"):
            await client.call_tool("reconnect", {})

        status_after_reconnect = await client.call_tool(
            "get_connection_status",
            {"broker": "Cached Plant"},
        )
        snapshot_after_reconnect = await client.call_tool(
            "get_broker_snapshot",
            {"broker": broker_id},
        )

    discovered = {str(item.id): item.name for item in brokers.data}
    assert discovered[broker_id] == "Cached Plant"
    assert "Local MQTT" in discovered.values()
    assert status.data.status == "disconnected"
    assert status_after_reconnect.data.status == "disconnected"
    assert status_after_reconnect.data.dropped_message_count == 0
    assert snapshot.data.connection_status == "disconnected"
    assert snapshot.data.connected_at is None
    assert snapshot.data.observation_started_at is None
    assert snapshot.data.topics[0].topic == "plant/temperature"
    assert snapshot.data.topics[0].payload.value == "21.5"
    assert snapshot.data.topics[0].source == "stored"
    assert "broker_disconnected" in snapshot.data.completeness.limitations
    assert "observation_not_started" in snapshot.data.completeness.limitations
    assert snapshot_after_reconnect.data.connection_status == "disconnected"
    assert snapshot_after_reconnect.data.topics[0].topic == "plant/temperature"
    assert snapshot_after_reconnect.data.topics[0].payload.value == "21.5"
    assert snapshot_after_reconnect.data.topics[0].source == "stored"
