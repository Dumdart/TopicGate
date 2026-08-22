# Install TopicGate for Codex

Codex can use TopicGate either as a standalone MCP server or through the bundled plugin. The plugin is the recommended setup because it also provides focused TopicGate skills.

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

Before connecting Codex, install TopicGate and use TopicGate Desktop to configure a broker, add subscriptions, and observe data. The MCP server reads the same local application-data directory as the desktop app.

## Development: install the plugin from a local checkout

From a TopicGate source checkout, add the checkout as a Codex plugin marketplace and install the bundled plugin:

```powershell
codex plugin marketplace add .
codex plugin add topicgate@topicgate
```

Enable the plugin and start a new Codex thread. Its default MCP configuration runs `topicgate --mode read-only`.

<p align="center">
  <img src="../images/plugin_in_codex.png" alt="TopicGate installed in Codex with its MCP server and skills enabled." width="720" />
</p>

Try one of these prompts:

```text
Help me set up TopicGate.
Inspect my TopicGate MQTT state.
Show the latest observed MQTT values.
```

## Install only the MCP server

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
