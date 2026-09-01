"""Run the Zigbee2MQTT demo contract against a disposable Mosquitto broker."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

import paho.mqtt.client as mqtt


DEMO_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEMO_DIR.parents[1]
COMPOSE_FILE = DEMO_DIR / "docker-compose.yml"
ENV_FILE = DEMO_DIR / ".env"
USERNAME = "topicgate"
PASSWORD = "topicgate-demo-password"


class Collector:
    def __init__(self, port: int, topic_filter: str = "zigbee2mqtt/#") -> None:
        self.messages: list[tuple[str, str, bool]] = []
        self._connected = threading.Event()
        self._subscribed = threading.Event()
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"topicgate-demo-smoke-{uuid4().hex}",
            protocol=mqtt.MQTTv5,
        )
        self._client.username_pw_set(USERNAME, PASSWORD)
        self._client.on_connect = self._on_connect
        self._client.on_subscribe = self._on_subscribe
        self._client.on_message = self._on_message
        self._topic_filter = topic_filter
        self._client.connect("localhost", port, keepalive=30)
        self._client.loop_start()
        if not self._connected.wait(10) or not self._subscribed.wait(10):
            self.close()
            raise TimeoutError("Timed out subscribing to the demo broker.")

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            return
        options = mqtt.SubscribeOptions(qos=1, retainAsPublished=True)
        client.subscribe(self._topic_filter, options=options)
        self._connected.set()

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties) -> None:
        self._subscribed.set()

    def _on_message(self, client, userdata, message) -> None:
        self.messages.append(
            (message.topic, message.payload.decode("utf-8"), message.retain)
        )

    def wait_for_topics(self, expected: set[str], timeout: float = 10) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if expected <= {topic for topic, _, _ in self.messages}:
                return
            time.sleep(0.05)
        observed = sorted({topic for topic, _, _ in self.messages})
        raise AssertionError(f"Expected {sorted(expected)}, observed {observed}")

    def close(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("localhost", 0))
        return listener.getsockname()[1]


def compose_command(project: str, *arguments: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-name",
        project,
        "-f",
        str(COMPOSE_FILE),
        "--env-file",
        str(ENV_FILE),
        *arguments,
    ]


def run_publisher(port: int, phase: str) -> None:
    environment = os.environ.copy()
    environment.update(MQTT_USERNAME=USERNAME, MQTT_PASSWORD=PASSWORD)
    subprocess.run(
        [
            sys.executable,
            str(DEMO_DIR / "publisher.py"),
            "--host",
            "localhost",
            "--port",
            str(port),
            "--phase",
            phase,
            "--once",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
    )


def assert_full_phase(port: int) -> None:
    expected_payloads = {
        "zigbee2mqtt/bridge/state": '{"state":"online"}',
        "zigbee2mqtt/bridge/devices": (
            '[{"friendly_name":"kitchen_sensor","type":"EndDevice"},'
            '{"friendly_name":"garage_sensor","type":"EndDevice"},'
            '{"friendly_name":"attic_sensor","type":"EndDevice"},'
            '{"friendly_name":"basement_freezer","type":"EndDevice"},'
            '{"friendly_name":"nursery_sensor","type":"EndDevice"}]'
        ),
        "zigbee2mqtt/garage_sensor/availability": '{"state":"offline"}',
        "zigbee2mqtt/attic_sensor/availability": '{"state":"online"}',
        "zigbee2mqtt/attic_sensor": (
            '{"battery":41,"humidity":67.2,'
            '"last_seen":"2000-01-01T00:00:00+00:00",'
            '"temperature":12.4}'
        ),
        "zigbee2mqtt/kitchen_sensor/availability": '{"state":"online"}',
        "zigbee2mqtt/kitchen_sensor": (
            '{"battery":96,"humidity":45.2,"linkquality":132,'
            '"temperature":21.3}'
        ),
        "zigbee2mqtt/basement_freezer": '{"temperature":-18.7}',
    }
    collector = Collector(port)
    try:
        run_publisher(port, "full")
        collector.wait_for_topics(set(expected_payloads))
        observed = {topic: payload for topic, payload, _ in collector.messages}
        assert observed == expected_payloads
        assert "zigbee2mqtt/nursery_sensor" not in observed
    finally:
        collector.close()


def assert_retained_disconnected_value(port: int) -> None:
    collector = Collector(port, "zigbee2mqtt/basement_freezer")
    try:
        collector.wait_for_topics({"zigbee2mqtt/basement_freezer"})
        assert collector.messages == [
            ("zigbee2mqtt/basement_freezer", '{"temperature":-18.7}', True)
        ]
    finally:
        collector.close()


def assert_healthy_phase_omits_attic_state(port: int) -> None:
    collector = Collector(port, "zigbee2mqtt/+")
    try:
        collector.wait_for_topics({"zigbee2mqtt/basement_freezer"})
        collector.messages.clear()
        run_publisher(port, "healthy")
        collector.wait_for_topics({"zigbee2mqtt/kitchen_sensor"})
        assert collector.messages == [
            (
                "zigbee2mqtt/kitchen_sensor",
                '{"battery":96,"humidity":45.2,"linkquality":132,'
                '"temperature":21.3}',
                False,
            )
        ]
    finally:
        collector.close()


def main() -> None:
    port = free_port()
    project = f"topicgate-zigbee2mqtt-smoke-{uuid4().hex[:12]}"
    environment = os.environ.copy()
    environment.update(
        MQTT_PORT=str(port),
        MQTT_USERNAME=USERNAME,
        MQTT_PASSWORD=PASSWORD,
    )
    try:
        subprocess.run(
            compose_command(project, "up", "-d", "--wait"),
            env=environment,
            check=True,
        )
        assert_full_phase(port)
        assert_retained_disconnected_value(port)
        assert_healthy_phase_omits_attic_state(port)
        print("Zigbee2MQTT demo smoke test passed.")
    finally:
        subprocess.run(
            compose_command(project, "down", "--volumes", "--remove-orphans"),
            env=environment,
            check=False,
        )


if __name__ == "__main__":
    main()
