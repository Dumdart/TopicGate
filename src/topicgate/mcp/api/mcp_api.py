from abc import ABC, abstractmethod
from fastmcp import FastMCP


class MCPApi(ABC):
    @abstractmethod
    def register(self, mcp: FastMCP) -> None:
        """Register a FastMCP instance with the MCP API."""


class McpApiContainer:
    def __init__(self, apis: list[MCPApi]):
        self.apis = apis

    def register(self, mcp: FastMCP) -> None:
        for api in self.apis:
            api.register(mcp)
