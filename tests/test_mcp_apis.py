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
from topicgate.mcp.api.broker_api import BrokerAPI
from topicgate.mcp.api.connection_api import ConnectionAPI
from topicgate.mcp.api.mcp_api import McpApiContainer
from topicgate.mcp.api.publish_api import PublishAPI
from topicgate.mcp.server import Server
from topicgate.mcp.api.subscription_api import SubscriptionAPI
from topicgate.mcp.api.topic_api import TopicAPI


def mcp_runtime() -> MagicMock:
    runtime = MagicMock()
    runtime.active_broker = SimpleNamespace(id=uuid4(), name="Primary")
    runtime.list_brokers.return_value = (runtime.active_broker,)
    runtime.connection_status = ConnectionStatus.DISCONNECTED
    runtime.dropped_message_count = 2
    runtime.topic_update_interval = 0.1
    runtime.get_connection_status.return_value = ConnectionStatus.DISCONNECTED
    runtime.get_dropped_message_count.return_value = 2
    runtime.get_topic_update_interval.return_value = 0.1
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
    runtime.activate_broker = AsyncMock(return_value=runtime.active_broker)
    return runtime


async def test_non_broker_apis_register_described_tools() -> None:
    async def scenario() -> None:
        runtime = mcp_runtime()
        mcp = FastMCP("test")
        McpApiContainer(
            [
                BrokerAPI(runtime),
                ConnectionAPI(runtime),
                PublishAPI(runtime),
                SubscriptionAPI(runtime),
                TopicAPI(runtime),
            ]
        ).register(mcp)

        async with Client(mcp) as client:
            tools = await client.list_tools()

        assert {item.name for item in tools} == {
            "activate_broker",
            "add_subscription",
            "connect",
            "disconnect",
            "get_connection_status",
            "get_topic_state",
            "list_brokers",
            "list_subscriptions",
            "list_topics",
            "publish",
            "reconnect",
            "remove_subscription",
            "update_subscription",
        }
        for item in tools:
            assert item.description is not None
            assert "Side effects:" in item.description
            assert "Required state:" in item.description
            assert "Identifiers:" in item.description
            assert "Failures:" in item.description

    await scenario()


async def test_subscription_api_maps_flat_arguments_to_domain_models() -> None:
    async def scenario() -> None:
        runtime = mcp_runtime()
        broker_id = runtime.active_broker.id
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

    await scenario()


async def test_remove_subscription_rejects_an_unknown_filter() -> None:
    async def scenario() -> None:
        runtime = mcp_runtime()

        with pytest.raises(ValueError, match="Unknown subscription filter"):
            await SubscriptionAPI(runtime).remove_subscription(
                runtime.active_broker.id,
                "missing/#",
            )

        runtime.remove_subscription.assert_not_awaited()

    await scenario()


def test_topic_api_returns_text_and_binary_safe_payload_views() -> None:
    runtime = mcp_runtime()
    broker_id = runtime.active_broker.id
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


async def test_connection_api_reports_status_and_delegates_commands() -> None:
    async def scenario() -> None:
        runtime = mcp_runtime()
        runtime.connection_status = ConnectionStatus.CONNECTED
        runtime.get_connection_status.return_value = ConnectionStatus.CONNECTED
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

    await scenario()


async def test_publish_api_supports_utf8_and_base64_payloads() -> None:
    async def scenario() -> None:
        runtime = mcp_runtime()
        broker_id = runtime.active_broker.id
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

    await scenario()


async def test_broker_scoped_apis_accept_profile_names() -> None:
    runtime = mcp_runtime()
    broker_id = runtime.active_broker.id
    runtime.list_topics.return_value = ("home/status",)
    runtime.list_subscriptions.return_value = (Subscription("home/#"),)

    assert TopicAPI(runtime).list_topics(" primary ") == ("home/status",)
    assert TopicAPI(runtime).get_topic_state("PRIMARY", "home/status") is None
    status = ConnectionAPI(runtime).get_connection_status("Primary")
    subscription_api = SubscriptionAPI(runtime)
    subscriptions = subscription_api.list_subscriptions("Primary")
    await subscription_api.add_subscription("Primary", "devices/#")
    await BrokerAPI(runtime).activate_broker("Primary")
    await PublishAPI(runtime).publish("Primary", "home/set", "on")

    assert status.broker_id == broker_id
    assert subscriptions == (Subscription("home/#"),)
    runtime.list_topics.assert_called_with(broker_id)
    runtime.get_topic_state.assert_called_with(broker_id, "home/status")
    runtime.get_connection_status.assert_called_with(broker_id)
    runtime.list_subscriptions.assert_called_with(broker_id)
    runtime.add_subscription.assert_awaited_once_with(
        broker_id,
        Subscription("devices/#"),
    )
    runtime.activate_broker.assert_awaited_once_with(broker_id)
    runtime.publish.assert_awaited_once_with(broker_id, "home/set", b"on")


async def test_legacy_mcp_call_shapes_remain_supported() -> None:
    runtime = mcp_runtime()
    mcp = FastMCP("test")
    McpApiContainer(
        [
            ConnectionAPI(runtime),
            SubscriptionAPI(runtime),
            TopicAPI(runtime),
        ]
    ).register(mcp)

    async with Client(mcp) as client:
        await client.call_tool("list_topics", {})
        await client.call_tool("get_connection_status", {})
        await client.call_tool(
            "get_topic_state",
            {
                "broker_id": str(runtime.active_broker.id),
                "topic": "home/status",
            },
        )
        await client.call_tool(
            "list_subscriptions",
            {"broker_id": str(runtime.active_broker.id)},
        )

    runtime.list_topics.assert_called_with(runtime.active_broker.id)
    runtime.get_topic_state.assert_called_with(
        runtime.active_broker.id,
        "home/status",
    )
    runtime.list_subscriptions.assert_called_with(runtime.active_broker.id)


async def test_server_lifespan_starts_disconnected_after_initial_connection_failure() -> None:
    async def scenario() -> None:
        server = Server.__new__(Server)
        server.services = MagicMock()
        server.services.start_services = AsyncMock(
            side_effect=ConnectionError("broker unavailable")
        )
        server.services.stop_services = AsyncMock()
        server.dependencies = MagicMock()
        server.dependencies.runtime.stop = AsyncMock()

        async with server._lifespan(MagicMock()):
            pass

        server.services.stop_services.assert_awaited_once_with()
        server.dependencies.runtime.stop.assert_awaited_once_with()

    await scenario()
