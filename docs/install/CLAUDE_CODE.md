# Install TopicGate for Claude Code

Claude Code can use TopicGate either through the bundled plugin or as a standalone stdio MCP server. The plugin is the recommended setup because it also installs the focused TopicGate skills.

Before connecting Claude Code, install TopicGate and use TopicGate Desktop to configure a broker, add subscriptions, and observe data. The MCP server reads the same local application-data directory as the desktop app.

## Install from a local checkout

From the TopicGate repository root, register the current directory as a local marketplace and install the plugin:

```powershell
claude plugin marketplace add .
claude plugin install topicgate@topicgate
```

The equivalent commands inside an interactive Claude Code session are:

```text
/plugin marketplace add .
/plugin install topicgate@topicgate
```

To load the plugin for one development session without installing it, use:

```powershell
claude --plugin-dir ./topicgate-plugin
```

The plugin automatically loads its skills and starts TopicGate in read-only mode. Restart Claude Code and open a new session after installing or updating the plugin.

## Install from GitHub

After the marketplace has been published, replace the local path with the GitHub repository:

```powershell
claude plugin marketplace add Dumdart/TopicGate
claude plugin install topicgate@topicgate
```

## Install only the MCP server

Use this when you do not want the plugin skills:

```powershell
claude mcp add topicgate -- topicgate --mode read-only
```

If `topicgate` is not on `PATH`, replace it with its absolute path. TopicGate Desktop's MCP setup page can copy a configuration with the resolved executable path.

## Control mode

Control mode can connect or disconnect brokers, change subscriptions, refresh observations, and publish MQTT messages. Use it only in a trusted environment:

```powershell
claude mcp add topicgate-control -- topicgate --mode control
```

Confirm the broker, topic, payload, and encoding before allowing a publish operation.
