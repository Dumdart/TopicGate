# TopicGate

TopicGate provides secure local access to MQTT topics through TopicGate Desktop, a focused application for inspecting live messages and managing subscription filters across multiple broker profiles.

## Features

- Monitor live MQTT topics and payloads.
- Inspect QoS, retained state, receive time, raw bytes, and message counts.
- Subscribe with exact MQTT paths or `+` and `#` wildcard filters.
- Create independent profiles for different MQTT brokers.
- Edit any profile without connecting to it first.
- Save broker settings without interrupting the active connection, or save and connect in one action.
- Retain profiles, active selection, and subscriptions in a local SQLite database.
- Store passwords in the operating system's secure credential store and keep
  live message values out of the database.

## Requirements

- Python 3.11 or newer
- Access to an MQTT 5-compatible broker
- A graphical desktop environment supported by PySide6

## Installation

Clone the repository, create a virtual environment, and install the project in editable mode.

### Windows PowerShell

```powershell
git clone https://github.com/Dumdart/TopicGate.git
cd TopicGate
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

### Linux or macOS

```bash
git clone https://github.com/Dumdart/TopicGate.git
cd TopicGate
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Configuration

No configuration file is required. A new installation starts with a local MQTT profile using `localhost:1883`. Edit that profile in TopicGate to set the broker host, port, username, password, and TLS option. SQLite stores the non-secret profile settings, while passwords are stored in Windows Credential Locker, macOS Keychain, or the available Linux Secret Service/KWallet backend.

## Running TopicGate Desktop

With the virtual environment active, use either entry point:

```powershell
topicgate
python -m topicgate
```

On Windows, the installed command is `topicgate.exe`.

If the initial MQTT connection fails, the application remains open in a disconnected state so the broker profile can be corrected.

## First-use workflow

1. Check the MQTT connection indicator in the top-right corner.
2. Open the broker profile menu above the observer tree.
3. Use **Edit profile...** to enter credentials or correct an existing profile, including an inactive one.
4. Choose **Save** to persist settings without connecting, or **Save & connect** to activate that profile.
5. Select **Add filter** and enter an MQTT subscription such as `home/+/temperature` or `devices/#`.
6. Select an observed topic to inspect its decoded and raw payload details.

## MQTT filters

Subscription filters are passed to the broker unchanged. Leading and trailing slashes remain significant, and standard MQTT wildcards are supported:

- `+` matches one topic level, for example `home/+/temperature`.
- `#` matches all remaining levels and must be the final segment, for example `devices/#`.

Topics discovered through wildcard subscriptions appear in the observer tree while they remain covered by an active filter.

## Local data

TopicGate stores `topicgate.db` in the platform application-data directory:

- Windows: `%LOCALAPPDATA%\Dumdart\TopicGate`
- Linux: `~/.local/share/TopicGate`
- macOS: `~/Library/Application Support/TopicGate`

Set `TOPICGATE_DATA_DIR` to use an explicit location. The database stores broker profile names and connection settings (excluding passwords), the active profile, and each profile's subscription filters and options. Passwords remain in the operating system credential store. Live MQTT payloads, message counters, and timestamps remain runtime-only.

To start with a new configuration, close TopicGate and move or delete `topicgate.db`. This permanently removes saved profiles and subscriptions unless the file is backed up first.

### Migrating from Smart Home Observer

Existing `smart_observer.db` data in the launch directory is migrated automatically on first TopicGate launch. The original file is retained as a recovery copy. If both old and new databases exist, TopicGate uses `topicgate.db` and does not merge them.

## Roadmap terminology

TopicGate Desktop is the currently available application. TopicGate Service, TopicGate API, and the future `topicgate-client` package are roadmap concepts and are not yet available.

## Development

Install the editable project as described above, then run:

```bash
python -m pytest -q
```

The project uses PySide6 and qasync for the desktop interface, paho-mqtt for MQTT communication, and SQLAlchemy with SQLite for persistence.

## License

TopicGate is available under the [MIT License](LICENCE).
