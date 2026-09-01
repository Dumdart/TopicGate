"""Publish a deterministic Zigbee2MQTT-shaped MQTT demo scenario."""

from __future__ import annotations

import argparse
import json
import os
import signal
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import paho.mqtt.client as mqtt


@dataclass(frozen=True)
class DemoCase:
    device: str
    condition: str
    topic: str
    evidence: str


DEMO_CASES = (
    DemoCase(
        "kitchen_sensor",
        "healthy",
        "zigbee2mqtt/kitchen_sensor",
        "Online availability and state refreshed every five seconds.",
    ),
    DemoCase(
        "garage_sensor",
        "offline",
        "zigbee2mqtt/garage_sensor/availability",
        "Availability is explicitly offline.",
    ),
    DemoCase(
        "attic_sensor",
        "stale",
        "zigbee2mqtt/attic_sensor",
        "State is published once with last_seen 24 hours in the past.",
    ),
    DemoCase(
        "basement_freezer",
        "retained/disconnected",
        "zigbee2mqtt/basement_freezer",
        "A short-lived client publishes retained state, then disconnects.",
    ),
    DemoCase(
        "nursery_sensor",
        "missing expected topic",
        "zigbee2mqtt/nursery_sensor",
        "Listed in bridge/devices but intentionally never published.",
    ),
)

EXPECTED_DEVICES = tuple(case.device for case in DEMO_CASES)
MISSING_TOPIC = "zigbee2mqtt/nursery_sensor"
HEALTHY_INTERVAL_SECONDS = 5.0


class PublishResult(Protocol):
    def wait_for_publish(self, timeout: float | None = None) -> Any: ...


class Publisher(Protocol):
    def publish(
        self, topic: str, payload: str, qos: int = 0, retain: bool = False
    ) -> PublishResult: ...


def encode(payload: object) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def bridge_devices_payload() -> str:
    return encode(
        [{"friendly_name": device, "type": "EndDevice"} for device in EXPECTED_DEVICES]
    )


def publish_message(
    client: Publisher,
    topic: str,
    payload: object,
    *,
    retain: bool = False,
) -> None:
    result = client.publish(topic, encode(payload), qos=1, retain=retain)
    result.wait_for_publish(timeout=5)


def publish_initial_state(client: Publisher, now: datetime) -> None:
    """Publish every case except the dedicated disconnected-publisher value."""
    publish_message(client, "zigbee2mqtt/bridge/state", {"state": "online"}, retain=True)
    client.publish(
        "zigbee2mqtt/bridge/devices", bridge_devices_payload(), qos=1, retain=True
    ).wait_for_publish(timeout=5)
    publish_message(
        client,
        "zigbee2mqtt/garage_sensor/availability",
        {"state": "offline"},
        retain=True,
    )
    publish_message(
        client,
        "zigbee2mqtt/attic_sensor/availability",
        {"state": "online"},
        retain=True,
    )
    publish_message(
        client,
        "zigbee2mqtt/attic_sensor",
        {
            "battery": 41,
            "humidity": 67.2,
            "last_seen": (now - timedelta(hours=24)).isoformat(),
            "temperature": 12.4,
        },
    )


def publish_healthy_state(client: Publisher, sequence: int, now: datetime) -> None:
    publish_message(
        client,
        "zigbee2mqtt/kitchen_sensor/availability",
        {"state": "online"},
        retain=True,
    )
    publish_message(
        client,
        "zigbee2mqtt/kitchen_sensor",
        {
            "battery": 96,
            "humidity": 45.0 + (sequence % 3) / 10,
            "last_seen": now.isoformat(),
            "linkquality": 132,
            "temperature": 21.0 + (sequence % 5) / 10,
        },
    )


def render_scenario_table() -> str:
    rows = [
        "| Device | Condition | Topic | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    rows.extend(
        f"| `{case.device}` | {case.condition} | `{case.topic}` | {case.evidence} |"
        for case in DEMO_CASES
    )
    return "\n".join(rows)


def new_client(client_id: str) -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv5,
    )
    client.username_pw_set(
        os.getenv("MQTT_USERNAME", "topicgate"),
        os.getenv("MQTT_PASSWORD", "topicgate-demo-password"),
    )
    return client


def connect(client: mqtt.Client, host: str, port: int) -> None:
    connected = threading.Event()

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            raise RuntimeError(f"MQTT connection failed: {reason_code}")
        connected.set()

    client.on_connect = on_connect
    client.connect(host, port, keepalive=30)
    client.loop_start()
    if not connected.wait(timeout=10):
        client.loop_stop()
        raise TimeoutError(f"Timed out connecting to MQTT broker at {host}:{port}")


def publish_disconnected_retained_value(
    host: str,
    port: int,
    now: datetime,
) -> None:
    ghost = new_client("topicgate-demo-disconnected-publisher")
    connect(ghost, host, port)
    try:
        publish_message(
            ghost,
            "zigbee2mqtt/basement_freezer",
            {"last_seen": now.isoformat(), "temperature": -18.7},
            retain=True,
        )
    finally:
        ghost.disconnect()
        ghost.loop_stop()


def run(host: str, port: int, *, once: bool = False) -> None:
    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())

    client = new_client("topicgate-demo-live-publisher")
    client.will_set(
        "zigbee2mqtt/bridge/state", encode({"state": "offline"}), qos=1, retain=True
    )
    connect(client, host, port)
    try:
        now = datetime.now(UTC)
        publish_initial_state(client, now)
        publish_disconnected_retained_value(host, port, now)
        publish_healthy_state(client, 0, now)
        print(f"Scenario ready on mqtt://{host}:{port}; Ctrl+C to stop.", flush=True)

        sequence = 1
        while not once and not stop.wait(HEALTHY_INTERVAL_SECONDS):
            publish_healthy_state(client, sequence, datetime.now(UTC))
            sequence += 1
    finally:
        client.disconnect()
        client.loop_stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument(
        "--once",
        action="store_true",
        help="Publish one deterministic cycle and exit.",
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Print the canonical scenario table.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.describe:
        print(render_scenario_table())
        return
    run(args.host, args.port, once=args.once)


if __name__ == "__main__":
    main()
