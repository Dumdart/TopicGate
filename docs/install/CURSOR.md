# Install TopicGate for Cursor

Cursor loads TopicGate through the portable Agent Plugins 1.0 package. The plugin installs eight TopicGate skills and starts the local MCP server in read-only mode.

Before installing the plugin, install TopicGate and use TopicGate Desktop to configure a broker, add subscriptions, and observe data. The MCP server reads the same local application-data directory as the desktop app.

## Test or install the plugin locally

From a TopicGate source checkout, copy the `topicgate-plugin` directory to Cursor's local plugin directory:

```powershell
$destination = Join-Path $env:USERPROFILE ".cursor\plugins\local\topicgate"
New-Item -ItemType Directory -Force -Path $destination
Copy-Item -Recurse -Force -Path ".\topicgate-plugin\*" -Destination $destination
```

Restart Cursor or run **Developer: Reload Window**. Open **Customize** and confirm that the TopicGate skills and MCP server are enabled. Skills appear under **Agent Decides** and can also be invoked with `/skill-name`.

Cursor caches the copied plugin. Repeat the copy and reload steps after changing the local plugin source.

Public one-click installation requires TopicGate to be submitted to and approved for the Cursor Marketplace. Until then, use the local installation above or distribute it through a Cursor team marketplace.

## Install only the MCP server

Use this project configuration when you want the MCP tools without the plugin skills. Create `.cursor/mcp.json` in the project:

```json
{
  "mcpServers": {
    "topicgate": {
      "command": "topicgate",
      "args": ["--mode", "read-only"]
    }
  }
}
```

If `topicgate` is not on `PATH`, replace it with its absolute path. TopicGate Desktop's MCP setup page can copy a configuration with the resolved executable path.

## Control mode

The installed plugin intentionally uses read-only mode. To expose operations that connect or disconnect brokers, change subscriptions, refresh observations, or publish MQTT messages, configure a separate project MCP server:

```json
{
  "mcpServers": {
    "topicgate-control": {
      "command": "topicgate",
      "args": ["--mode", "control"]
    }
  }
}
```

Use control mode only in a trusted project. Confirm the broker, topic, payload, and encoding before allowing a publish operation.
