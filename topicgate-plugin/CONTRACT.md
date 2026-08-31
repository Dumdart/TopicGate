# TopicGate plugin contract

- Supports TopicGate 1.x and MCP contract `1.0`.
- Uses Agent Plugins 1.0 contracts validated by the repository tests for Codex, Claude Code, GitHub Copilot, and Cursor.
- `.mcp.json` and `mcp.json` are read-only. Use `.mcp-control.json` only for intentional connection, subscription, observation, or publish changes.
- TopicGate Desktop owns credentials, retention, cache deletion, and complex maintenance.
