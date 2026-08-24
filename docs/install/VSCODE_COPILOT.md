# Install TopicGate for VS Code and GitHub Copilot

TopicGate is packaged as an Agent Plugins 1.0 plugin for GitHub Copilot in VS Code and GitHub Copilot CLI.

Before configuring VS Code or GitHub Copilot, follow the [main TopicGate setup guide](../../README.md#get-started) to install TopicGate, launch Desktop, and configure a broker. Then return here for host-specific setup.

## Install in VS Code

Agent plugins require a current VS Code release with GitHub Copilot and the `chat.plugins.enabled` setting enabled.

Add the TopicGate marketplace to your VS Code `settings.json`:

```json
"chat.plugins.marketplaces": [
  "Dumdart/TopicGate"
]
```

Open the Extensions view, search for `@agentPlugins`, select TopicGate, and choose **Install**. You can also run **Chat: Open Customizations**, open the **Plugins** tab, and install TopicGate from the marketplace there.

After installation, start a new chat. The skills appear in **Chat: Configure Skills**, and the `topicgate` server appears under **MCP: List Servers**.

## Install with GitHub Copilot CLI

Add the TopicGate GitHub repository as a marketplace and install the plugin:

```powershell
copilot plugin marketplace add Dumdart/TopicGate
copilot plugin install topicgate@topicgate
```

VS Code automatically discovers plugins installed by GitHub Copilot CLI. Start a new Copilot session and use `/skills list` to confirm that the TopicGate skills loaded.

## MCP server only

Use this workspace configuration when you want the MCP tools without the plugin skills. Create `.vscode/mcp.json` in the workspace:

```json
{
  "servers": {
    "topicgate": {
      "type": "stdio",
      "command": "topicgate",
      "args": ["--mode", "read-only"]
    }
  }
}
```

If `topicgate` is not on `PATH`, replace it with its absolute path. TopicGate Desktop's MCP setup page can copy a configuration with the resolved executable path.

## Control mode

The installed plugin intentionally uses read-only mode. To expose operations that connect or disconnect brokers, change subscriptions, refresh observations, or publish MQTT messages, configure a separate workspace MCP server:

```json
{
  "servers": {
    "topicgate-control": {
      "type": "stdio",
      "command": "topicgate",
      "args": ["--mode", "control"]
    }
  }
}
```

Use control mode only in a trusted workspace. Confirm the broker, topic, payload, and encoding before allowing a publish operation.
