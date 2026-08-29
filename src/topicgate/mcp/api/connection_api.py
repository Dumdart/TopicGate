from uuid import UUID

from fastmcp import FastMCP
from fastmcp.tools import tool

from topicgate.app.services.broker_resolver import BrokerResolver
from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.mcp.api.mcp_api import MCPApi
from topicgate.mcp.models import ConnectionStatusResult


class ConnectionAPI(MCPApi):
    def __init__(
        self,
        runtime: TopicGateRuntime,
        resolver: BrokerResolver,
    ):
        self._runtime = runtime
        self._resolver = resolver

    def register(self, mcp: FastMCP, *, control_enabled: bool = False) -> None:
        mcp.add_tool(self.get_connection_status)
        if control_enabled:
            mcp.add_tool(self.connect)
            mcp.add_tool(self.disconnect)
            mcp.add_tool(self.reconnect)

    @tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def get_connection_status(
        self,
        broker: UUID | str | None = None,
    ) -> ConnectionStatusResult:
        """Get connection health for a selected broker profile.

        Side effects: None; this does not activate or connect a broker.
        Required state: Omit broker only when an active profile exists.
        Identifiers: broker accepts a UUID or unique case-insensitive name.
        Failures: Fails for no active profile or unknown or ambiguous profiles.
        """
        resolved = self._resolver.resolve_or_active(broker)
        return ConnectionStatusResult(
            broker_id=resolved.id,
            status=str(self._runtime.get_connection_status(resolved.id)),
            dropped_message_count=self._runtime.get_dropped_message_count(
                resolved.id
            ),
            topic_update_interval=self._runtime.get_topic_update_interval(
                resolved.id
            ),
        )

    @tool(annotations={"openWorldHint": True})
    async def connect(self) -> None:
        """Connect the active MQTT broker profile.

        Side effects: Opens an MQTT connection and starts receiving messages.
        Required state: An active broker with usable credentials must exist.
        Identifiers: This tool always targets the active broker; it takes no ID.
        Failures: Fails without an active profile or when connection setup fails.
        """
        await self._runtime.connect()

    @tool(annotations={"openWorldHint": True})
    async def disconnect(self) -> None:
        """Disconnect the active MQTT broker profile.

        Side effects: Closes the active MQTT connection and stops observation.
        Required state: An active broker profile must exist.
        Identifiers: This tool always targets the active broker; it takes no ID.
        Failures: Fails without an active profile or when disconnection fails.
        """
        await self._runtime.disconnect()

    @tool(annotations={"openWorldHint": True})
    async def reconnect(self) -> None:
        """Reconnect the active MQTT broker profile.

        Side effects: Closes and reopens the MQTT connection and resumes messages.
        Required state: An active broker with usable credentials must exist.
        Identifiers: This tool always targets the active broker; it takes no ID.
        Failures: Fails without an active profile or when reconnection fails.
        """
        await self._runtime.reconnect()
