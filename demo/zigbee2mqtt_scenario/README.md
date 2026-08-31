# Zigbee2MQTT scenario

This hardware-free scenario gives TopicGate a stable set of healthy and unhealthy
MQTT evidence for documentation, regression tests, screenshots, and live demos.
The broker is disposable, so old retained topics cannot leak between runs.

## Run it

From the repository root, start the authenticated Mosquitto broker:

```powershell
docker compose -f demo/zigbee2mqtt_scenario/docker-compose.yml `
  --env-file demo/zigbee2mqtt_scenario/.env up -d --wait
```

Configure TopicGate with `localhost:1883`, username `topicgate`, password
`topicgate-demo-password`, and subscription `zigbee2mqtt/#`, then connect before
starting the publisher. This ordering lets TopicGate observe the attic message
once and watch it age while the kitchen comparison continues to refresh:

```powershell
uv run python demo/zigbee2mqtt_scenario/publisher.py
```

Leave the publisher running while taking screenshots or giving a demonstration.
Stop it with Ctrl+C, then remove the disposable broker:

```powershell
docker compose -f demo/zigbee2mqtt_scenario/docker-compose.yml `
  --env-file demo/zigbee2mqtt_scenario/.env down
```

For a quick command-line inspection:

```powershell
docker compose -f demo/zigbee2mqtt_scenario/docker-compose.yml exec mosquitto `
  mosquitto_sub -h localhost -u topicgate -P topicgate-demo-password `
  -t "zigbee2mqtt/#" -v
```

## Canonical scenario

<!-- scenario-table:start -->
| Device | Condition | Topic | Evidence |
| --- | --- | --- | --- |
| `kitchen_sensor` | healthy | `zigbee2mqtt/kitchen_sensor` | Online availability and state refreshed every five seconds. |
| `hallway_light` | online | `zigbee2mqtt/hallway_light/availability` | Availability is explicitly online. |
| `garage_sensor` | offline | `zigbee2mqtt/garage_sensor/availability` | Availability is explicitly offline. |
| `attic_sensor` | stale | `zigbee2mqtt/attic_sensor` | State is published once with last_seen 24 hours in the past. |
| `basement_freezer` | retained/disconnected | `zigbee2mqtt/basement_freezer` | A short-lived client publishes retained state, then disconnects. |
| `nursery_sensor` | missing expected topic | `zigbee2mqtt/nursery_sensor` | Listed in bridge/devices but intentionally never published. |
<!-- scenario-table:end -->

`zigbee2mqtt/bridge/devices` is the machine-readable inventory. It lists all six
devices, including `nursery_sensor`; the absence of `zigbee2mqtt/nursery_sensor`
is therefore observable evidence rather than an undocumented assumption.

The table above is rendered from `DEMO_CASES` in `publisher.py`. A regression test
guards the documentation and the MQTT publication plan against drift. Run
`uv run python demo/zigbee2mqtt_scenario/publisher.py --describe` to print it.
