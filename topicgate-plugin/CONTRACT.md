# TopicGate plugin contract

This plugin supports TopicGate 1.x and the TopicGate MCP contract `1.0`.
It is tested with FastMCP 3.4.7 and the Codex and Claude Code plugin ingestion
contracts used by the repository test suite.

The installed `.mcp.json` is read-only. Control mode is a separate, explicit
configuration in `.mcp-control.json`; copy it only when connection changes,
subscription changes, observation refresh, and publishing are intended.

TopicGate Desktop remains the owner of broker credentials, retention policy,
cache deletion, and other destructive or complex maintenance.
