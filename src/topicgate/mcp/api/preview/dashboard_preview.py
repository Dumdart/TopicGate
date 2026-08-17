"""FastMCP Apps development entry point for the TopicGate dashboard."""
from topicgate.mcp.capabilities import McpMode
from topicgate.mcp.server import Server


mcp = Server(McpMode.CONTROL).mcp
