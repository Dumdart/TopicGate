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
        """Return already observed or persisted state without activating a broker."""
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
        """Activate, reconnect, briefly observe, and snapshot a broker profile."""
        return await self._snapshot_service.observe(
            broker,
            topic_filter=topic_filter,
            max_age_seconds=max_age_seconds,
            result_limit=limit,
            payload_limit_bytes=payload_limit_bytes,
            wait_seconds=wait_seconds,
        )
