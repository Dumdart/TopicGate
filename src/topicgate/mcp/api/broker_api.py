from uuid import UUID

from fastmcp import FastMCP
from fastmcp.tools import tool

from topicgate.app.services.broker_resolver import BrokerResolver
from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.core.models.broker_summary import BrokerSummary
from topicgate.mcp.api.mcp_api import MCPApi


class BrokerAPI(MCPApi):
    def __init__(
        self,
        runtime: TopicGateRuntime,
        resolver: BrokerResolver | None = None,
    ):
        self._runtime = runtime
        self._resolver = resolver or BrokerResolver(runtime)

    def register(self, mcp: FastMCP) -> None:
        mcp.add_tool(self.list_brokers)
        mcp.add_tool(self.activate_broker)

    @tool(annotations={"readOnlyHint": True})
    def list_brokers(self) -> tuple[BrokerSummary, ...]:
        return self._runtime.list_brokers()

    @tool()
    async def activate_broker(self, broker_id: UUID | str) -> BrokerSummary:
        resolved = self._resolver.resolve(broker_id)
        return await self._runtime.activate_broker(resolved.id)
