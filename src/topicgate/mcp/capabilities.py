from enum import StrEnum


class McpMode(StrEnum):
    """Capability boundary for tools exposed by the MCP server."""

    READ_ONLY = "read-only"
    CONTROL = "control"

    @property
    def control_enabled(self) -> bool:
        return self is McpMode.CONTROL
