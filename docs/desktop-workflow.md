# TopicGate Desktop workflow

The desktop opens with a first-run checklist. Work through it in order:

![TopicGate first-run checklist](images/desktop-first-run-checklist.png)

1. Select **Configure** to enter a broker host, port, credentials, and TLS setting. Use **Save & reconnect** to test the profile immediately.
2. Select **Connect** (or use the header control) and confirm that the status says **Connected**.
3. Select **Add filter** and enter the MQTT filter that covers the values you want to inspect.
4. Select **Reconnect & observe** to intentionally interrupt the connection, renew it, and collect a fresh snapshot. This makes the distinction between persisted and new observations visible.
5. Select **MCP setup** and copy the read-only configuration into the MCP host you use. Restart that host after adding the server. Choose `--mode control` only for a trusted host that is allowed to change broker state or publish.

## Reading the workspace

The observer pane explains empty states in place:

- **No subscriptions** means TopicGate has no topic filter to observe.
- **Disconnected** means values may be cached and old until reconnection.
- **Filtered** means the current snapshot controls omit all matching values.
- **Only persisted values** means the displayed values were restored from local storage; use Details to inspect their source and age before acting on them.

The Snapshot panel includes a legend: **Live** was received during the current run; **Cached** was restored from local storage; **Stale** predates the observation window; and **Stored** identifies persisted provenance. Snapshot completeness and limitations always apply to the whole result, not just the selected topic.

## Cache safety

Open **File > Stored observations** to review retention limits and persisted cache usage. Yellow warnings appear when a broker or global count/payload limit reaches the configured warning threshold. Deletion dialogs identify their scope, broker, entry count, bytes, and time range before permanent removal. A partial deletion means an entry changed after the preview and was safely skipped.

## Keyboard and recovery

- `Ctrl+F` focuses the topic search.
- `Ctrl+N` opens Add filter.
- `Ctrl+Shift+S` opens Stored observations.
- `Ctrl+Shift+M` opens MCP setup.
- Standard Tab, Shift+Tab, Enter, and Space navigation works for all new controls; labels expose descriptive accessible names.

Connection and broker-profile actions are disabled while a connection, reconnect, broker switch, or profile deletion is already running. If a broker operation fails, TopicGate offers recovery actions to retry the connection or edit the profile instead of requiring the user to diagnose a generic error.

## Desktop reference image

The screenshot uses the first-run checklist only, so no broker names, topics, values, or credentials are published. The checklist, empty-state guidance, source/freshness legend, and retention banner are native widgets; they scale with system text size and remain available to assistive technology.
