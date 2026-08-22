# TopicGate installation recovery and upgrades

## Upgrade

Upgrade an installation managed by uv:

```powershell
uv tool upgrade topicgate
```

Or upgrade a pip installation:

```powershell
python -m pip install --upgrade topicgate
```

Start `topicgate-gui` or `topicgate` after upgrading. TopicGate automatically updates its local database before it opens it.

## Uninstall

Remove a uv-managed installation:

```powershell
uv tool uninstall topicgate
```

Or remove a pip installation:

```powershell
python -m pip uninstall topicgate
```

Uninstalling the package does not remove local data or broker passwords. Remove or update any MCP host configuration that still starts `topicgate` before uninstalling.

## `topicgate` is not on `PATH`

Open a new terminal after installation, then check whether the executable is available:

```powershell
Get-Command topicgate
```

If it is still unavailable, use the recovery path for the installation method you chose:

For a uv tool installation, add its executable directory to `PATH` and reopen the terminal:

```powershell
uv tool update-shell
uv tool dir --bin
```

For a pip installation, run the server through that Python interpreter:

```powershell
python -m topicgate --mode read-only
```

For a host configuration, use the absolute executable path copied from TopicGate Desktop's MCP setup page. That page also includes the data-directory environment variable needed to share the desktop application's data.

## Data and backups

TopicGate stores profiles, subscriptions, settings, and observed MQTT state in `topicgate.db`. Passwords are stored separately in the operating-system credential store.

| Platform | Default data directory |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Dumdart\TopicGate` |
| Linux | `~/.local/share/TopicGate` |
| macOS | `~/Library/Application Support/TopicGate` |

Set `TOPICGATE_DATA_DIR` to use a different directory.

To back up TopicGate, stop the desktop app and every MCP host that runs TopicGate, then copy the entire data directory to a safe location. Copying the whole directory preserves `topicgate.db` and any SQLite WAL sidecar files. On Windows, for example:

```powershell
Copy-Item -Recurse -Force "$env:LOCALAPPDATA\Dumdart\TopicGate" "$env:USERPROFILE\Documents\TopicGate-backup"
```

Restore a backup only while TopicGate is stopped.

## Database migrations

TopicGate runs database migrations automatically when the desktop application or MCP server starts. A concurrent desktop and MCP startup is coordinated so only one migration runs at a time. You do not need to run Alembic manually.

Back up the data directory before a major upgrade. If startup reports a migration failure, stop every TopicGate process, copy the data directory, and retry once. Do not delete the database or operating-system credentials as the first recovery step.

## Safe reset

To reset profiles, settings, subscriptions, and observed state while preserving broker passwords:

1. Stop TopicGate Desktop and every MCP host using TopicGate.
2. Back up the entire data directory.
3. Rename the data directory instead of deleting it.
4. Start `topicgate-gui`; TopicGate creates a new database and fresh local profiles.

For example, on Windows:

```powershell
Rename-Item "$env:LOCALAPPDATA\Dumdart\TopicGate" "TopicGate.backup-20260822"
```

The reset does not delete passwords because they are not stored in the database. The old credential entries remain unused because the new profiles have new IDs. To intentionally remove a broker password, delete its profile in TopicGate Desktop before resetting; profile deletion removes the matching operating-system credential. Do not manually clear `TopicGate MQTT` credential-store entries unless you intend to remove those passwords permanently.
