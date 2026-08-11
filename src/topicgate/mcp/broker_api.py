from uuid import UUID

from fastmcp.server.server import FastMCP
from fastmcp.tools import tool

from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.core.models.broker_summary import BrokerSummary
from topicgate.mcp.mcp_api import McpApi


class BrokerAPI(McpApi):
    def __init__(self, runtime: TopicGateRuntime):
        self._runtime = runtime

    def register(self, mcp: FastMCP) -> None:
        mcp.add_tool(self.list_brokers)
        mcp.add_tool(self.activate_broker)

    @tool(annotations={"readOnlyHint": True})
    def list_brokers(self) -> tuple[BrokerSummary, ...]:
        return self._runtime.list_brokers()

    @tool()
    async def activate_broker(self, broker_id: UUID) -> BrokerSummary:
        return await self._runtime.activate_broker(broker_id)
