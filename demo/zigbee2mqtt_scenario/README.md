# Zigbee2MQTT scenario

This hardware-free demo combines a disposable local Mosquitto broker with a
small Zigbee2MQTT-shaped publisher. It provides deterministic topics and
payloads for screenshots, regression checks, and live demonstrations.

## Prerequisites

- Docker with Docker Compose
- Python 3.11 or newer
- `uv` with the project dependencies installed
- Bash, such as Git Bash on Windows

From the repository root, install the development dependencies if needed:

```console
uv sync --extra apps --extra test
```

## Start the scenario

Run the broker and publisher together:

```bash
bash demo/zigbee2mqtt_scenario/run_demo.sh
```

Keep this terminal open. The script:

1. Loads the broker settings from `.env`.
2. Starts the authenticated Mosquitto container and waits for it to become healthy.
3. Runs `publisher.py`, which refreshes the healthy device every five seconds.
4. Stops and removes the disposable broker when the publisher exits.

Press Ctrl+C when the demo is finished. Starting with a fresh broker also
prevents retained topics from an earlier scenario version from reappearing.

## Configure TopicGate with the CLI

While the scenario is running, open a second terminal in the repository root and
create the broker profile:

```console
uv run topicgate-cli profile add \
  --name "Zigbee2MQTT Demo" \
  --host localhost \
  --port 1883 \
  --username topicgate
```

When prompted, enter the demo password:

```text
topicgate-demo-password
```

Then add the scenario subscription:

```console
uv run topicgate-cli sub add \
  --name "Zigbee2MQTT Demo" \
  --topic "zigbee2mqtt/#" \
  --retain-as-published
```

Both commands are safe to run again: the CLI reuses the existing profile and
accepts an existing subscription. Start TopicGate Desktop or the MCP server after
creating the profile. If either process was already running, restart it so it
reloads the externally created profile, then connect `Zigbee2MQTT Demo`.

For Desktop:

```console
uv run topicgate-gui
```

For the read-only MCP server:

```console
uv run topicgate
```

## Interpret the results

TopicGate's state badge describes observation provenance, not device health:

- **Live** means TopicGate received the MQTT message during the current process.
- The garage device reports **offline** inside its decoded availability payload.
- The attic sensor's old `last_seen` value is payload evidence of staleness; it
  does not change TopicGate's observation badge.
- The basement value is marked retained even though its publisher disconnected.
- The nursery topic is intentionally absent. Its expected presence is established
  by `zigbee2mqtt/bridge/devices`.

Non-retained sensor values are visible only while TopicGate is connected. The
kitchen value refreshes every five seconds, but the attic value is published only
once at scenario startup.

## Inspect MQTT directly

To inspect retained values and future publications without TopicGate, run this in
another terminal:

```bash
docker compose -f demo/zigbee2mqtt_scenario/docker-compose.yml exec mosquitto \
  mosquitto_sub -h localhost -u topicgate -P topicgate-demo-password \
  -t "zigbee2mqtt/#" -v
```

## Canonical scenario

<!-- scenario-table:start -->
| Device | Condition | Topic | Evidence |
| --- | --- | --- | --- |
| `kitchen_sensor` | healthy | `zigbee2mqtt/kitchen_sensor` | Online availability and state refreshed every five seconds. |
| `garage_sensor` | offline | `zigbee2mqtt/garage_sensor/availability` | Availability is explicitly offline. |
| `attic_sensor` | stale | `zigbee2mqtt/attic_sensor` | State is published once with last_seen 24 hours in the past. |
| `basement_freezer` | retained/disconnected | `zigbee2mqtt/basement_freezer` | A short-lived client publishes retained state, then disconnects. |
| `nursery_sensor` | missing expected topic | `zigbee2mqtt/nursery_sensor` | Listed in bridge/devices but intentionally never published. |
<!-- scenario-table:end -->

`zigbee2mqtt/bridge/devices` is the machine-readable inventory. It lists all five
devices, including `nursery_sensor`; the absence of `zigbee2mqtt/nursery_sensor`
is therefore observable evidence rather than an undocumented assumption.

The table above is rendered from `DEMO_CASES` in `publisher.py`. A regression test
guards the documentation and the MQTT publication plan against drift. Run
`uv run python demo/zigbee2mqtt_scenario/publisher.py --describe` to print it.
