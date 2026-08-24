# Install TopicGate for Codex

Codex can use TopicGate as an MCP server or through the bundled skills plugin.

Before configuring Codex, follow the [main TopicGate setup guide](../../README.md#get-started) to install TopicGate, launch Desktop, and configure a broker. Then return here for Codex-specific setup.

## Install the plugin from GitHub

Add the TopicGate GitHub repository as a marketplace and install the plugin:

```powershell
codex plugin marketplace add Dumdart/TopicGate
codex plugin add topicgate@topicgate
```

Start a new Codex thread after installation. The plugin runs `topicgate --mode read-only`.

<p align="center">
  <img src="../images/plugin_in_codex.png" alt="TopicGate installed in Codex with its MCP server and skills enabled." width="720" />
</p>

Try one of these prompts:

```text
Help me set up TopicGate.
Inspect my TopicGate MQTT state.
Show the latest observed MQTT values.
```

## MCP server only

Use this when you do not want the plugin skills:

```powershell
codex mcp add topicgate -- topicgate --mode read-only
```

If the executable is not on `PATH`, replace `topicgate` with its absolute path. TopicGate Desktop's MCP setup page can copy a configuration with that path already resolved.

## Control mode

Control mode exposes operations that can connect or disconnect brokers, change subscriptions, refresh observations, and publish MQTT messages. Add it only to a trusted Codex environment:

```powershell
codex mcp add topicgate-control -- topicgate --mode control
```

Confirm the broker, topic, payload, and encoding before allowing a publish operation.
