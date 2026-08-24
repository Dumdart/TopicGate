# Install TopicGate for Cursor

Cursor loads TopicGate through the portable Agent Plugins 1.0 package.

Before configuring Cursor, follow the [main TopicGate setup guide](../../README.md#get-started) to install TopicGate, launch Desktop, and configure a broker. Then return here for Cursor-specific setup.

## Install the plugin from GitHub

Cursor requires the full repository URL when adding the TopicGate marketplace:

```powershell
cursor-agent plugin marketplace add https://github.com/Dumdart/TopicGate
```

Run `cursor-agent`, enter `/plugin`, open the **Marketplace** tab, and install TopicGate. Choose user or project scope when prompted. The installed plugin is also available in the Cursor IDE.

## MCP server only

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
