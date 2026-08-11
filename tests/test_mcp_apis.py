import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastmcp import Client, FastMCP

from topicgate.core.models.connection_status import ConnectionStatus
from topicgate.core.models.observer_model import TopicState
from topicgate.core.models.subscription import Subscription
from topicgate.mcp.connection_api import ConnectionAPI
from topicgate.mcp.mcp_api import McpApiContainer
from topicgate.mcp.publish_api import PublishAPI
from topicgate.mcp.subscription_api import SubscriptionAPI
from topicgate.mcp.topic_api import TopicAPI


def mcp_runtime() -> MagicMock:
    runtime = MagicMock()
    runtime.active_broker = SimpleNamespace(id=uuid4())
    runtime.connection_status = ConnectionStatus.DISCONNECTED
    runtime.dropped_message_count = 2
    runtime.topic_update_interval = 0.1
    runtime.list_subscriptions.return_value = ()
    runtime.list_topics.return_value = ()
    runtime.get_topic_state.return_value = None
    runtime.add_subscription = AsyncMock()
    runtime.update_subscription = AsyncMock()
    runtime.remove_subscription = AsyncMock()
    runtime.connect = AsyncMock()
    runtime.disconnect = AsyncMock()
    runtime.reconnect = AsyncMock()
    runtime.publish = AsyncMock()
    return runtime


def test_non_broker_apis_register_described_tools() -> None:
    async def scenario() -> None:
        runtime = mcp_runtime()
        mcp = FastMCP("test")
        McpApiContainer(
            [
                ConnectionAPI(runtime),
                PublishAPI(runtime),
                SubscriptionAPI(runtime),
                TopicAPI(runtime),
            ]
        ).register(mcp)

        async with Client(mcp) as client:
            tools = await client.list_tools()

        assert {item.name for item in tools} == {
            "add_subscription",
            "connect",
            "disconnect",
            "get_connection_status",
            "get_topic_state",
            "list_subscriptions",
            "list_topics",
            "publish",
            "reconnect",
            "remove_subscription",
            "update_subscription",
        }
        assert all(item.description for item in tools)

    asyncio.run(scenario())


def test_subscription_api_maps_flat_arguments_to_domain_models() -> None:
    async def scenario() -> None:
        runtime = mcp_runtime()
        broker_id = uuid4()
        original = Subscription("home/#", qos=1, id=7)
        runtime.list_subscriptions.return_value = (original,)
        api = SubscriptionAPI(runtime)

        await api.add_subscription(broker_id, "devices/+", qos=2)
        await api.update_subscription(
            broker_id,
            "devices/+",
            "devices/#",
            retain_as_published=True,
            retain_handling=1,
        )
        await api.remove_subscription(broker_id, "home/#")

        runtime.add_subscription.assert_awaited_once_with(
            broker_id,
            Subscription("devices/+", qos=2),
        )
        runtime.update_subscription.assert_awaited_once_with(
            broker_id,
            "devices/+",
            Subscription(
                "devices/#",
                retain_as_published=True,
                retain_handling=1,
            ),
        )
        runtime.remove_subscription.assert_awaited_once_with(broker_id, original)

    asyncio.run(scenario())


def test_remove_subscription_rejects_an_unknown_filter() -> None:
    async def scenario() -> None:
        runtime = mcp_runtime()

        with pytest.raises(ValueError, match="Unknown subscription filter"):
            await SubscriptionAPI(runtime).remove_subscription(uuid4(), "missing/#")

        runtime.remove_subscription.assert_not_awaited()

    asyncio.run(scenario())


def test_topic_api_returns_text_and_binary_safe_payload_views() -> None:
    runtime = mcp_runtime()
    broker_id = uuid4()
    received_at = datetime.now(timezone.utc)
    api = TopicAPI(runtime)

    runtime.get_topic_state.return_value = TopicState(
        "status",
        "home/status",
        b"online",
        1,
        True,
        received_at,
    )
    text_result = api.get_topic_state(broker_id, "home/status")

    assert text_result is not None
    assert text_result.payload_text == "online"
    assert text_result.payload_base64 == "b25saW5l"
    assert text_result.received_at == received_at

    runtime.get_topic_state.return_value = TopicState(
        "image",
        "camera/image",
        b"\xff\x00",
        0,
        False,
        received_at,
    )
    binary_result = api.get_topic_state(broker_id, "camera/image")

    assert binary_result is not None
    assert binary_result.payload_text is None
    assert binary_result.payload_base64 == "/wA="


def test_connection_api_reports_status_and_delegates_commands() -> None:
    async def scenario() -> None:
        runtime = mcp_runtime()
        runtime.connection_status = ConnectionStatus.CONNECTED
        api = ConnectionAPI(runtime)

        result = api.get_connection_status()
        await api.connect()
        await api.disconnect()
        await api.reconnect()

        assert result.broker_id == runtime.active_broker.id
        assert result.status == "connected"
        assert result.dropped_message_count == 2
        runtime.connect.assert_awaited_once_with()
        runtime.disconnect.assert_awaited_once_with()
        runtime.reconnect.assert_awaited_once_with()

    asyncio.run(scenario())


def test_publish_api_supports_utf8_and_base64_payloads() -> None:
    async def scenario() -> None:
        runtime = mcp_runtime()
        broker_id = uuid4()
        api = PublishAPI(runtime)

        await api.publish(broker_id, "home/set", "p\u00e5")
        await api.publish(broker_id, "camera/set", "/wA=", "base64")

        assert runtime.publish.await_args_list[0].args == (
            broker_id,
            "home/set",
            "p\u00e5".encode("utf-8"),
        )
        assert runtime.publish.await_args_list[1].args == (
            broker_id,
            "camera/set",
            b"\xff\x00",
        )

        with pytest.raises(ValueError, match="not valid base64"):
            await api.publish(broker_id, "camera/set", "%%%", "base64")

    asyncio.run(scenario())
