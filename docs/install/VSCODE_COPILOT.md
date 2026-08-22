# Install TopicGate for VS Code and GitHub Copilot

TopicGate is packaged as an Agent Plugins 1.0 plugin for GitHub Copilot in VS Code and GitHub Copilot CLI. The plugin installs eight TopicGate skills and starts the local MCP server in read-only mode.

## Install TopicGate

TopicGate's official MCP Registry identifier is `io.github.Dumdart/topicgate`. The registry provides package metadata rather than installing packages; after a release has been published, registry-aware clients can discover TopicGate with that identifier. Install the released PyPI package before connecting an MCP host:

```powershell
uv tool install topicgate
topicgate-gui
```

Alternatively:

```powershell
python -m pip install topicgate
topicgate-gui
```

Before installing the plugin, install TopicGate and use TopicGate Desktop to configure a broker, add subscriptions, and observe data. The MCP server reads the same local application-data directory as the desktop app.

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

For local development, from the TopicGate repository root, register the current directory as a local marketplace and install the plugin:

```powershell
copilot plugin marketplace add .
copilot plugin install topicgate@topicgate
```

VS Code automatically discovers plugins installed by GitHub Copilot CLI. Start a new Copilot session and use `/skills list` to confirm that the TopicGate skills loaded.

To install from GitHub after the marketplace has been published, use `Dumdart/TopicGate` instead of `.`:

```powershell
copilot plugin marketplace add Dumdart/TopicGate
copilot plugin install topicgate@topicgate
```

## Install only the MCP server

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
