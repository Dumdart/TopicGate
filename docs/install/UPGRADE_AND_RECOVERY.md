# Upgrade and recover TopicGate

## Upgrade or uninstall

```console
uv tool upgrade topicgate
uv tool uninstall topicgate
```

For pip installations:

```console
python -m pip install --upgrade topicgate
python -m pip uninstall topicgate
```

TopicGate applies database migrations at startup. Uninstalling the package does not remove data or broker passwords.

## Executable not found

Open a new terminal. For `uv`, run `uv tool update-shell` and inspect `uv tool dir --bin`. For pip, run `python -m topicgate --mode read-only`. Agent hosts may use the absolute executable path copied from TopicGate Desktop's MCP setup page.

## Data and backups

| Platform | Default data directory |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Dumdart\TopicGate` |
| Linux | `~/.local/share/TopicGate` |
| macOS | `~/Library/Application Support/TopicGate` |

Set `TOPICGATE_DATA_DIR` to override the location. The directory contains `topicgate.db` and may contain SQLite WAL sidecars; passwords remain in the operating-system credential store.

To back up or restore, stop TopicGate Desktop and every TopicGate MCP process, then copy the entire data directory.

## Recovery reset

1. Stop every TopicGate process.
2. Back up the data directory.
3. Rename the data directory.
4. Start `topicgate-gui` to create fresh local data.

This resets profiles, settings, subscriptions, and observations but not credential-store entries. Delete a profile through TopicGate Desktop when you intend to remove its password.
