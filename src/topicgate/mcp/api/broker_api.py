from uuid import UUID

from fastmcp import FastMCP
from fastmcp.tools import tool

from topicgate.app.models.broker_inspection import BrokerInspection
from topicgate.app.services.broker_inspection_service import BrokerInspectionService
from topicgate.app.services.broker_resolver import BrokerResolver
from topicgate.app.services.broker_snapshot_service import DEFAULT_SNAPSHOT_RESULT_LIMIT
from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.core.models.broker_summary import BrokerSummary
from topicgate.core.payload_limits import MAX_RENDERED_PAYLOAD_BYTES
from topicgate.mcp.api.mcp_api import MCPApi


class BrokerAPI(MCPApi):
    def __init__(
        self,
        runtime: TopicGateRuntime,
        resolver: BrokerResolver,
        inspection_service: BrokerInspectionService,
    ):
        self._runtime = runtime
        self._resolver = resolver
        self._inspection_service = inspection_service

    def register(self, mcp: FastMCP, *, control_enabled: bool = False) -> None:
        mcp.add_tool(self.list_brokers)
        mcp.add_tool(self.inspect_broker)
        if control_enabled:
            mcp.add_tool(self.activate_broker)

    @tool(annotations={"readOnlyHint": True})
    def list_brokers(self) -> tuple[BrokerSummary, ...]:
        """List persisted broker profiles.

        Side effects: None; this does not activate or connect a broker.
        Required state: The local TopicGate database must be available.
        Identifiers: Returned IDs are broker UUIDs; names are profile labels.
        Failures: Fails when persisted broker profiles cannot be read.
        """
        return self._runtime.list_brokers()

    @tool(annotations={"readOnlyHint": True})
    def inspect_broker(
        self,
        broker: UUID | str,
        include_snapshot: bool = False,
        snapshot_limit: int = DEFAULT_SNAPSHOT_RESULT_LIMIT,
        payload_limit_bytes: int = MAX_RENDERED_PAYLOAD_BYTES,
    ) -> BrokerInspection:
        """Inspect a broker profile with its passive runtime and stored state.

        Side effects: None; this does not activate, connect, wait, or refresh.
        Required state: The broker profile and local database must be available.
        Identifiers: broker accepts a UUID or unique case-insensitive name.
        Failures: Fails for invalid selectors or snapshot bounds and read errors.
        """
        return self._inspection_service.inspect(
            broker,
            include_snapshot=include_snapshot,
            snapshot_limit=snapshot_limit,
            payload_limit_bytes=payload_limit_bytes,
        )

    @tool()
    async def activate_broker(self, broker_id: UUID | str) -> BrokerSummary:
        """Make a broker profile active and connect it.

        Side effects: Disconnects the current client, changes the active profile,
        and connects to the selected MQTT broker.
        Required state: The selected profile and its credentials must be usable.
        Identifiers: broker_id accepts a UUID or unique case-insensitive name.
        Failures: Fails for unknown or ambiguous profiles and connection errors.
        """
        resolved = self._resolver.resolve(broker_id)
        return await self._runtime.activate_broker(resolved.id)
