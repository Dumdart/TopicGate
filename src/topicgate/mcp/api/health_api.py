from datetime import datetime
from uuid import UUID

from fastmcp import FastMCP
from fastmcp.tools import tool

from topicgate.app.models.expectation_health_report import (
    ExpectationHealthReport,
    FailureHistoryResult,
)
from topicgate.app.services.broker_resolver import BrokerResolver
from topicgate.app.services.health_expectation_service import (
    DEFAULT_STALE_AFTER_SECONDS,
)
from topicgate.app.services.health_query_service import (
    DEFAULT_HEALTH_RESULT_LIMIT,
    HealthQueryService,
)
from topicgate.mcp.api.mcp_api import MCPApi


class HealthAPI(MCPApi):
    def __init__(
        self,
        query_service: HealthQueryService,
        resolver: BrokerResolver,
    ) -> None:
        self._query_service = query_service
        self._resolver = resolver

    def register(self, mcp: FastMCP, *, control_enabled: bool = False) -> None:
        mcp.add_tool(self.query_failure_history)
        if control_enabled:
            mcp.add_tool(self.get_health_report)

    @tool(annotations={"readOnlyHint": False})
    def get_health_report(
        self,
        broker: UUID | str,
        stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
        limit: int = DEFAULT_HEALTH_RESULT_LIMIT,
    ) -> ExpectationHealthReport:
        """Freshly evaluate bounded expectation health for a broker.

        Side effects: May persist health transitions and failure episodes locally;
        it never activates, connects, waits for, or publishes to MQTT.
        Required state: The broker profile and local health database must exist.
        Identifiers: broker accepts a UUID or unique case-insensitive profile name.
        Failures: Fails for unknown or ambiguous brokers, invalid bounds, or health
        evaluation and persistence errors.
        """
        resolved = self._resolver.resolve(broker)
        return self._query_service.get_health_report(
            resolved.id,
            stale_after_seconds=stale_after_seconds,
            limit=limit,
        )

    @tool(annotations={"readOnlyHint": True})
    def query_failure_history(
        self,
        broker: UUID | str,
        topic: str | None = None,
        status: str = "all",
        after: datetime | None = None,
        before: datetime | None = None,
        cursor: int | None = None,
        limit: int = DEFAULT_HEALTH_RESULT_LIMIT,
    ) -> FailureHistoryResult:
        """Query a bounded page of persisted expectation failures.

        Side effects: None; this reads local failure history only.
        Required state: The broker profile and local health database must exist.
        Identifiers: broker accepts a UUID or unique case-insensitive profile name;
        topic is an exact MQTT topic and status is all, active, or recovered.
        Failures: Fails for unknown or ambiguous brokers, invalid time ranges,
        cursors, status values, or result limits.
        """
        resolved = self._resolver.resolve(broker)
        return self._query_service.query_failure_history(
            broker_id=resolved.id,
            topic=topic,
            status=status,
            after=after,
            before=before,
            cursor=cursor,
            limit=limit,
        )

