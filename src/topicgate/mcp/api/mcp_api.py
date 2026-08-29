from abc import ABC, abstractmethod
from fastmcp import FastMCP


class MCPApi(ABC):
    @abstractmethod
    def register(self, mcp: FastMCP, *, control_enabled: bool = False) -> None:
        """Register a FastMCP instance with the MCP API."""
class McpApiContainer:
    def __init__(self, apis: list[MCPApi], *, control_enabled: bool = False):
        self.apis = apis
        self.control_enabled = control_enabled

    def register(self, mcp: FastMCP) -> None:
        for api in self.apis:
            api.register(mcp, control_enabled=self.control_enabled)
