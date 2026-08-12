from fastmcp import FastMCP
from fastmcp.tools import tool

from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.mcp.api.mcp_api import MCPApi
from topicgate.mcp.models import ConnectionStatusResult


class ConnectionAPI(MCPApi):
    def __init__(self, runtime: TopicGateRuntime):
        self._runtime = runtime

    def register(self, mcp: FastMCP) -> None:
        mcp.add_tool(self.get_connection_status)
        mcp.add_tool(self.connect)
        mcp.add_tool(self.disconnect)
        mcp.add_tool(self.reconnect)

    @tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def get_connection_status(self) -> ConnectionStatusResult:
        """Get connection health for the active MQTT broker profile."""
        return ConnectionStatusResult(
            broker_id=self._runtime.active_broker.id,
            status=str(self._runtime.connection_status),
            dropped_message_count=self._runtime.dropped_message_count,
            topic_update_interval=self._runtime.topic_update_interval,
        )

    @tool(annotations={"openWorldHint": True})
    async def connect(self) -> None:
        """Connect the active MQTT broker profile."""
        await self._runtime.connect()

    @tool(annotations={"openWorldHint": True})
    async def disconnect(self) -> None:
        """Disconnect the active MQTT broker profile."""
        await self._runtime.disconnect()

    @tool(annotations={"openWorldHint": True})
    async def reconnect(self) -> None:
        """Reconnect the active MQTT broker profile."""
        await self._runtime.reconnect()
