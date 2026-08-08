# Smart Home Observer

Smart Home Observer is a desktop MQTT explorer for watching smart-home topics, inspecting live message values, and managing subscription filters across multiple broker profiles.

The application is designed for people who operate or troubleshoot MQTT-based devices and want a focused graphical view without setting up a general-purpose MQTT development tool.

## Features

- Monitor live MQTT topics and payloads.
- Inspect QoS, retained state, receive time, raw bytes, and message counts.
- Subscribe with exact MQTT paths or `+` and `#` wildcard filters.
- Create independent profiles for different MQTT brokers.
- Edit any profile without connecting to it first.
- Save broker settings without interrupting the active connection, or save and connect in one action.
- Retain profiles, active selection, and subscriptions in a local SQLite database.
- Keep passwords and live message values out of the database.

## Requirements

- Python 3.11 or newer
- Access to an MQTT 5-compatible broker
- A graphical desktop environment supported by PySide6

## Installation

Clone the repository, create a virtual environment, and install the project in editable mode.

### Windows PowerShell

```powershell
git clone https://github.com/Dumdart/SmartHomeObserver.git
cd SmartHomeObserver
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
Copy-Item .env.example .env
```

### Linux or macOS

```bash
git clone https://github.com/Dumdart/SmartHomeObserver.git
cd SmartHomeObserver
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
cp .env.example .env
```

## Configuration

Edit `.env` before the first launch:

```dotenv
MQTT_HOST=192.168.1.20
MQTT_PORT=1883
MQTT_USERNAME=smart_home_bridge
MQTT_PASSWORD=change-me-mqtt-password
MQTT_USE_TLS=false
```

For a new database, these values initialize the default broker profile. After initialization, SQLite is the source of truth for the broker host, port, username, TLS setting, active profile, and subscriptions.

The application asks for the active broker password at launch. The entered value is held in memory only. Submitting an empty password uses `MQTT_PASSWORD` from `.env` as a fallback.

Both `.env` and `smart_observer.db` are ignored by Git.

## Running the application

With the virtual environment active:

```powershell
smart-home-observer
```

On Windows, `smart-home-observer.exe` is equivalent.

If the initial MQTT connection fails, the application remains open in a disconnected state so the broker profile can be corrected.

## First-use workflow

1. Enter the active broker password when prompted.
2. Check the MQTT connection indicator in the top-right corner.
3. Open the broker profile menu above the observer tree.
4. Use **Edit profile...** to correct an existing profile, including an inactive one.
5. Choose **Save** to persist settings without connecting, or **Save & connect** to activate that profile.
6. Select **Add filter** and enter an MQTT subscription such as `home/+/temperature` or `devices/#`.
7. Select an observed topic to inspect its decoded and raw payload details.

## MQTT filters

Subscription filters are passed to the broker unchanged. Leading and trailing slashes remain significant, and standard MQTT wildcards are supported:

- `+` matches one topic level, for example `home/+/temperature`.
- `#` matches all remaining levels and must be the final segment, for example `devices/#`.

Topics discovered through wildcard subscriptions appear in the observer tree while they remain covered by an active filter.

## Local data

The application creates `smart_observer.db` in the directory from which it is launched. The database stores:

- broker profile names and connection settings, excluding passwords;
- which profile is active;
- each profile's subscription filters and options.

Live MQTT payloads, message counters, timestamps, and passwords remain runtime-only.

To start with a new configuration, close the application and move or delete `smart_observer.db`. This permanently removes the saved profiles and subscriptions unless the file is backed up first.

## Development

Install the editable project as described above, then run:

```bash
python -m pytest -q
```

The project uses PySide6 and qasync for the desktop interface, paho-mqtt for MQTT communication, and SQLAlchemy with SQLite for persistence.

## License

Smart Home Observer is available under the [MIT License](LICENCE).
