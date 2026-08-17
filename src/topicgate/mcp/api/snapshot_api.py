from uuid import UUID

from fastmcp import FastMCP
from fastmcp.tools import tool

from topicgate.app.models.broker_snapshot import BrokerSnapshot
from topicgate.app.services.broker_snapshot_service import (
    DEFAULT_SNAPSHOT_RESULT_LIMIT,
    DEFAULT_SNAPSHOT_WAIT_SECONDS,
    BrokerSnapshotService,
)
from topicgate.core.payload_limits import MAX_RENDERED_PAYLOAD_BYTES
from topicgate.mcp.api.mcp_api import MCPApi


class SnapshotAPI(MCPApi):
    def __init__(self, snapshot_service: BrokerSnapshotService):
        self._snapshot_service = snapshot_service

    def register(self, mcp: FastMCP) -> None:
        mcp.add_tool(self.get_broker_snapshot)
        mcp.add_tool(self.observe_broker_snapshot)

    @tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_broker_snapshot(
        self,
        broker: UUID | str,
        topic_filter: str = "#",
        max_age_seconds: float | None = None,
        limit: int = DEFAULT_SNAPSHOT_RESULT_LIMIT,
        payload_limit_bytes: int = MAX_RENDERED_PAYLOAD_BYTES,
    ) -> BrokerSnapshot:
        """Return already observed or persisted state for a broker.

        Side effects: None; this never activates, connects, or waits for a broker.
        Required state: The broker profile must already exist locally.
        Identifiers: broker accepts a UUID or unique case-insensitive name;
        topic_filter accepts MQTT wildcards.
        Failures: Fails for an invalid broker, filter, age, limit, or payload limit,
        and when persisted state cannot be read.
        """
        return await self._snapshot_service.build(
            broker,
            topic_filter=topic_filter,
            max_age_seconds=max_age_seconds,
            result_limit=limit,
            payload_limit_bytes=payload_limit_bytes,
        )

    @tool(annotations={"readOnlyHint": False, "openWorldHint": True})
    async def observe_broker_snapshot(
        self,
        broker: UUID | str,
        topic_filter: str = "#",
        max_age_seconds: float | None = None,
        limit: int = DEFAULT_SNAPSHOT_RESULT_LIMIT,
        payload_limit_bytes: int = MAX_RENDERED_PAYLOAD_BYTES,
        wait_seconds: float = DEFAULT_SNAPSHOT_WAIT_SECONDS,
    ) -> BrokerSnapshot:
        """Activate, reconnect, briefly observe, and snapshot a broker profile.

        Side effects: Changes the active broker, reconnects MQTT, waits, receives
        messages, persists observations, and leaves the selected broker active.
        Required state: The profile and credentials must permit a connection.
        Identifiers: broker accepts a UUID or unique case-insensitive name;
        topic_filter accepts MQTT wildcards.
        Failures: Fails for invalid selectors or bounds, missing credentials,
        connection errors, or snapshot persistence/read errors.
        """
        return await self._snapshot_service.observe(
            broker,
            topic_filter=topic_filter,
            max_age_seconds=max_age_seconds,
            result_limit=limit,
            payload_limit_bytes=payload_limit_bytes,
            wait_seconds=wait_seconds,
        )
