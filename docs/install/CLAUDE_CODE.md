# Connect TopicGate to Claude Code

First [install TopicGate](OS_INSTALL.md), run `topicgate-gui`, and configure a broker.

```console
claude plugin marketplace add Dumdart/TopicGate
claude plugin install topicgate@topicgate
```

Restart Claude Code. The plugin loads TopicGate skills and runs the MCP server in read-only mode.

To use only MCP:

```console
claude mcp add topicgate -- topicgate --mode read-only
```

Trusted environments may opt into control tools:

```console
claude mcp add topicgate-control -- topicgate --mode control
```

Control mode can change connections, subscriptions, observations, and device state. Confirm publish details before use.
