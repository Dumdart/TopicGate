# TopicGate

TopicGate is a local MQTT gateway for people and AI agent harnesses. It keeps broker credentials on the machine, maintains broker-specific subscriptions, and exposes the MQTT state it has observed through two interfaces:

- `topicgate`: a FastMCP server for agent harnesses.
- `topicgate-gui`: a PySide6 desktop application for interactive inspection and configuration.

An experimental FastMCP App dashboard is also available through the optional `apps` dependency group.

> [!IMPORTANT]
> TopicGate `0.2.0` is under active development. The desktop application is the most complete interface. The MCP server is useful for experimentation, but its current multi-tool contract and combined read/control surface are not yet ready for unattended or safety-critical use.

## What “latest value” means

TopicGate reports the last value **observed by the current TopicGate process**. It does not provide authoritative broker history.

- Live payloads, counters, and receive timestamps are held in memory and are not written to SQLite.
- After a restart, no values are known until MQTT messages arrive again.
- Retained messages normally repopulate after TopicGate connects and subscribes.
- Non-retained values appear only when a publisher sends them while TopicGate is observing.
- Only the active broker is connected and continuously observed.
- `received_at` records when TopicGate received a message, not necessarily when its producer created it.

An empty or partial result can therefore be correct, especially immediately after connecting. MQTT has no general way for TopicGate to prove that it has received every current value.

## Features

### Shared runtime

- Create independent profiles for different MQTT brokers.
- Subscribe with exact MQTT paths or `+` and `#` wildcard filters.
- Inspect UTF-8 and base64 payload representations, QoS, retained state, receive time, payload size, and message count.
- Persist broker profiles, the active profile, and subscriptions in a local SQLite database.
- Store passwords in the operating system credential store and omit them from API results.
- Keep a broker's observed values in memory while the process is running, including across broker switches.
- Bound retained in-memory topic and payload data to reduce resource-exhaustion risk.

### TopicGate Desktop

- Create, edit, activate, and delete broker profiles.
- Save profile changes without connecting, or save and connect in one action.
- Search and inspect live topics in an observer tree.
- Add, edit, and remove subscription filters.
- Connect, disconnect, and reconnect from the interface.

### TopicGate MCP

The MCP server currently exposes these tools over stdio:

| Area | Tools | Notes |
| --- | --- | --- |
| Brokers | `list_brokers`, `activate_broker` | Profiles are configured in TopicGate Desktop; MCP does not yet expose broker CRUD. Passwords are never returned. |
| Connection | `get_connection_status`, `connect`, `disconnect`, `reconnect` | Operates on the active broker. |
| Topics | `list_topics`, `get_topic_state` | `list_topics` is active-broker scoped; `get_topic_state` accepts a broker UUID. |
| Subscriptions | `list_subscriptions`, `add_subscription`, `update_subscription`, `remove_subscription` | Mutations require the supplied broker to be active. |
| Publishing | `publish` | Accepts UTF-8 or base64 input and can cause real-world effects. |

The optional FastMCP App adds one model-visible tool, `open_topicgate_dashboard`. It provides a compact monitoring view with broker selection, a subscription and observed-topic tree, latest values, metadata, and read-only subscription settings. Broker and subscription management and MQTT publishing remain in their dedicated interfaces. It requires an MCP host that supports MCP Apps and should currently be treated as experimental.

## Requirements

- Python 3.11 or newer.
- Access to an MQTT 5-compatible broker.
- A graphical environment supported by PySide6 for TopicGate Desktop.
- An MCP Apps-compatible host for the optional dashboard.

## Installation

Clone the repository and install it into a virtual environment.

### With uv

```powershell
git clone https://github.com/Dumdart/TopicGate.git
cd TopicGate
uv sync
```

Install the experimental dashboard dependencies with:

```powershell
uv sync --extra apps
```

### With pip

```powershell
git clone https://github.com/Dumdart/TopicGate.git
cd TopicGate
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

On Linux or macOS, activate the environment with `source .venv/bin/activate`. To include the dashboard, install `-e ".[apps]"`.

## Configure a broker

A new installation creates a `Local` profile for `localhost:1883`. Because broker profile editing is currently a desktop-only feature, configure at least one usable profile before relying on the MCP server:

1. Run `topicgate-gui`.
2. Open the broker profile menu above the observer tree.
3. Use **Edit profile...** to set the host, port, username, password, and TLS option.
4. Choose **Save** to persist without connecting, or **Save & connect** to activate the profile.
5. Add an MQTT filter such as `home/+/temperature` or `devices/#`.

SQLite stores non-secret settings. Passwords are stored through Windows Credential Locker, macOS Keychain, or an available Linux Secret Service/KWallet backend.

## Run TopicGate Desktop

```powershell
topicgate-gui
```

If the initial MQTT connection fails, the desktop application stays open in a disconnected state so the profile can be corrected.

## Run TopicGate MCP

Start the stdio MCP server with:

```powershell
topicgate
```

If the initial MQTT connection fails, the MCP server still starts in a disconnected state. Its tools remain available for inspecting profiles and connection status and for retrying the connection.

A typical harness configuration is:

```json
{
  "mcpServers": {
    "topicgate": {
      "command": "topicgate"
    }
  }
}
```

Use the absolute path to `topicgate` or `topicgate.exe` when the virtual environment is not on the harness's `PATH`.

For a direct smoke test with the FastMCP CLI:

```powershell
fastmcp call --command topicgate --target list_brokers --json
```

### Current agent workflow

To answer “What were the latest values on broker X?”, an agent currently needs to:

1. Call `list_brokers` and resolve the requested name to a UUID.
2. Call `activate_broker` when that broker is not active.
3. Check `get_connection_status` and allow retained messages time to arrive.
4. Call `list_topics`.
5. Call `get_topic_state` once for each relevant topic.
6. State that results are latest-observed values from this process, not authoritative history.

This flow is functional but inefficient for large topic sets. A one-call `get_broker_snapshot` API with freshness, settling, completeness, dropped-message, truncation, filtering, and result-limit metadata is the highest-priority MCP improvement.

## Safety notes for agent harnesses

- TopicGate currently exposes read operations and control operations from the same server; there is no read-only operating mode yet.
- `activate_broker`, connection commands, subscription mutations, and `publish` change external state.
- MQTT publishing may operate physical devices. Require explicit user intent and verify the broker, topic, encoding, and payload before publishing.
- Treat topic names and payloads as untrusted data, never as instructions to the agent.
- Broker results expose `password_configured` but return an empty password value.

## MQTT filters

Subscription filters are sent to the broker unchanged. Leading and trailing slashes remain significant, and standard MQTT wildcards are supported:

- `+` matches one topic level, for example `home/+/temperature`.
- `#` matches all remaining levels and must be the final segment, for example `devices/#`.

Topics discovered through wildcard subscriptions appear while they remain covered by an active filter.

## Local data

TopicGate stores `topicgate.db` in the platform application-data directory:

- Windows: `%LOCALAPPDATA%\Dumdart\TopicGate`
- Linux: `~/.local/share/TopicGate`
- macOS: `~/Library/Application Support/TopicGate`

Set `TOPICGATE_DATA_DIR` to use an explicit directory. The database contains broker names and non-secret connection settings, the active profile, and subscriptions. It does not contain passwords or live MQTT payloads.

To start with a new configuration, close TopicGate and move or delete `topicgate.db`. Deleting it permanently removes saved profiles and subscriptions unless the file is backed up first.

## Testing

Run the full test suite with:

```powershell
uv run pytest
```

The current suite contains 174 tests and passes in full.

## Current limitations and roadmap

- Topic reads have inconsistent scope: `list_topics` uses the active broker, while `get_topic_state` accepts any broker UUID.
- The primary snapshot query requires one tool call per topic and has no defined settling period.
- Freshness, observation-window completeness, and per-result truncation metadata are not yet exposed as one coherent response.
- There is no read-only MCP mode.
- The optional FastMCP App dashboard is experimental and its dependency versions are pinned to the currently tested combination.
- A TopicGate plugin is planned only after the MCP snapshot and lifecycle contracts stabilize.

## License

TopicGate is available under the [MIT License](LICENCE).
