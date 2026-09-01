# Install TopicGate by operating system

TopicGate requires Python 3.11+ and access to an MQTT 5-compatible broker. Use an isolated `uv` tool installation where possible.

| Platform | Status |
| --- | --- |
| Windows Desktop | Verified; primary release environment. |
| Ubuntu Desktop | Verified with desktop startup, broker connection, subscriptions, and restart/reconnect. |
| Ubuntu Server | Passwordless read-only MCP is partially verified; authenticated unattended use is unsupported. |
| Other Linux distributions and macOS | Not verified end to end. |

## Windows

Install with `uv`:

```powershell
uv tool install topicgate
```

Or install with pip:

```powershell
python -m pip install topicgate
```

Run TopicGate Desktop:

```powershell
topicgate-gui
```

Passwords are stored in Windows Credential Locker.

## Ubuntu Desktop

Do not use `sudo pip` or `pip --break-system-packages`. Install with `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv tool install --python 3.11 topicgate
uv tool update-shell
```

Open a new terminal, or update the current shell, then start the desktop from the logged-in graphical session:

```bash
export PATH="$(uv tool dir --bin):$PATH"
unset PYTHON_KEYRING_BACKEND
topicgate --help
topicgate-gui
```

Do not run the desktop with `sudo` or through SSH. PySide6 and the Secret Service credential store require the logged-in desktop session. After configuring a password-protected broker, verify reconnection after a complete logout and login.

## Headless broker configuration

The `topicgate-cli` command configures broker profiles and subscriptions without starting the desktop. Add a profile with an MQTT password prompt:

```console
topicgate-cli profile add --name "Home" --host mqtt.example.com --port 1883 --username topicgate
```

Use `--use-tls` to enable TLS or `--no-password` to skip the password prompt for a passwordless broker. Existing profile names are left unchanged, so the command can be safely repeated. List profiles or test every configured profile with:

```console
topicgate-cli profile list
topicgate-cli profile test
```

Add and remove subscriptions by profile name:

```console
topicgate-cli sub add --name "Home" --topic "home/+/temperature" --qos 1
topicgate-cli sub remove --name "Home" --topic "home/+/temperature"
```

Subscription QoS can be `0`, `1`, or `2`. The optional `--retain-as-published` flag preserves the broker's retain flag, and `--retain-handling` accepts `0`, `1`, or `2`.

> Profiles created by the headless command become available to newly started TopicGate processes immediately. Restart an already-running desktop or MCP process to reload externally created profiles.

## Ubuntu Server

The CLI, migrations, disconnected read-only startup, and clean shutdown have been manually verified without PySide6. Use `topicgate-cli` for passwordless headless broker configuration.

Authenticated unattended operation is unsupported because Secret Service may be locked or unavailable after SSH login. Do not use plaintext keyrings, `keyrings.alt`, or database edits as production workarounds. A null keyring is suitable only for passwordless testing.

## Verify

```console
topicgate --help
topicgate-gui
```

Then configure a broker, connect, add a bounded subscription, restart TopicGate, and verify reconnection. See [Upgrades and recovery](UPGRADE_AND_RECOVERY.md) for maintenance and troubleshooting.
