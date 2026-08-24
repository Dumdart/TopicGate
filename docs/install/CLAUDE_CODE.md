# Install TopicGate for Claude Code

Claude Code can use TopicGate as an MCP server or through the bundled skills plugin.

Before configuring Claude Code, follow the [main TopicGate setup guide](../../README.md#get-started) to install TopicGate, launch Desktop, and configure a broker. Then return here for Claude-specific setup.

## Install the plugin from GitHub

Add the TopicGate GitHub repository as a marketplace and install the plugin:

```powershell
claude plugin marketplace add Dumdart/TopicGate
claude plugin install topicgate@topicgate
```

The equivalent commands inside an interactive Claude Code session are:

```text
/plugin marketplace add Dumdart/TopicGate
/plugin install topicgate@topicgate
```

The plugin automatically loads its skills and starts TopicGate in read-only mode. Restart Claude Code and open a new session after installing or updating the plugin.

## MCP server only

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
