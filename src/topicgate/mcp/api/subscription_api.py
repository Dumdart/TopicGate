from uuid import UUID

from fastmcp import FastMCP
from fastmcp.tools import tool

from topicgate.app.services.broker_resolver import BrokerResolver
from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.core.models.subscription import Subscription
from topicgate.mcp.api.mcp_api import MCPApi


class SubscriptionAPI(MCPApi):
    def __init__(
        self,
        runtime: TopicGateRuntime,
        resolver: BrokerResolver | None = None,
    ):
        self._runtime = runtime
        self._resolver = resolver or BrokerResolver(runtime)

    def register(self, mcp: FastMCP) -> None:
        mcp.add_tool(self.list_subscriptions)
        mcp.add_tool(self.add_subscription)
        mcp.add_tool(self.update_subscription)
        mcp.add_tool(self.remove_subscription)

    @tool(annotations={"readOnlyHint": True})
    def list_subscriptions(
        self,
        broker_id: UUID | str,
    ) -> tuple[Subscription, ...]:
        """List subscriptions for a broker UUID or profile name."""
        resolved = self._resolver.resolve(broker_id)
        return self._runtime.list_subscriptions(resolved.id)

    @tool(annotations={"openWorldHint": True})
    async def add_subscription(
        self,
        broker_id: UUID | str,
        topic_filter: str,
        qos: int = 1,
        retain_as_published: bool = False,
        retain_handling: int = 0,
    ) -> None:
        """Add an MQTT subscription to the active broker profile."""
        resolved = self._resolver.resolve(broker_id)
        await self._runtime.add_subscription(
            resolved.id,
            Subscription(
                topic_filter=topic_filter,
                qos=qos,
                retain_as_published=retain_as_published,
                retain_handling=retain_handling,
            ),
        )

    @tool(annotations={"openWorldHint": True})
    async def update_subscription(
        self,
        broker_id: UUID | str,
        original_filter: str,
        topic_filter: str,
        qos: int = 1,
        retain_as_published: bool = False,
        retain_handling: int = 0,
    ) -> None:
        """Replace an MQTT subscription on the active broker profile."""
        resolved = self._resolver.resolve(broker_id)
        await self._runtime.update_subscription(
            resolved.id,
            original_filter,
            Subscription(
                topic_filter=topic_filter,
                qos=qos,
                retain_as_published=retain_as_published,
                retain_handling=retain_handling,
            ),
        )

    @tool(
        annotations={
            "destructiveHint": True,
            "openWorldHint": True,
        }
    )
    async def remove_subscription(
        self,
        broker_id: UUID | str,
        topic_filter: str,
    ) -> None:
        """Remove an MQTT subscription from the active broker profile."""
        resolved = self._resolver.resolve(broker_id)
        subscription = next(
            (
                item
                for item in self._runtime.list_subscriptions(resolved.id)
                if item.topic_filter == topic_filter
            ),
            None,
        )
        if subscription is None:
            raise ValueError(f"Unknown subscription filter: {topic_filter}")
        await self._runtime.remove_subscription(resolved.id, subscription)
