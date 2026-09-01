import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from demo.zigbee2mqtt_scenario import publisher


class PublishResult:
    def wait_for_publish(self, timeout=None):
        return None


class RecordingClient:
    def __init__(self):
        self.messages = []

    def publish(self, topic, payload, qos=0, retain=False):
        self.messages.append((topic, json.loads(payload), qos, retain))
        return PublishResult()

    def disconnect(self):
        self.messages.append(("disconnect", None, None, None))

    def loop_stop(self):
        self.messages.append(("loop_stop", None, None, None))


def test_initial_scenario_has_expected_anomalies_and_omits_missing_topic():
    client = RecordingClient()
    now = datetime(2026, 8, 29, 10, 0, tzinfo=UTC)

    publisher.publish_initial_state(client, now)

    messages = {topic: (payload, retain) for topic, payload, _, retain in client.messages}
    assert set(messages) == {
        "zigbee2mqtt/attic_sensor",
        "zigbee2mqtt/attic_sensor/availability",
        "zigbee2mqtt/bridge/devices",
        "zigbee2mqtt/bridge/state",
        "zigbee2mqtt/garage_sensor/availability",
    }
    inventory = {
        device["friendly_name"]
        for device in messages["zigbee2mqtt/bridge/devices"][0]
    }
    assert inventory == set(publisher.EXPECTED_DEVICES)
    assert len(inventory) == 5
    assert publisher.MISSING_TOPIC not in messages
    assert messages["zigbee2mqtt/garage_sensor/availability"][0] == {"state": "offline"}
    assert messages["zigbee2mqtt/attic_sensor"][0]["last_seen"] == "2026-08-28T10:00:00+00:00"


def test_healthy_device_refreshes_with_non_retained_state():
    client = RecordingClient()
    now = datetime(2026, 8, 29, 10, 0, tzinfo=UTC)

    publisher.publish_healthy_state(client, sequence=3, now=now)

    messages = {topic: (payload, retain) for topic, payload, _, retain in client.messages}
    assert messages["zigbee2mqtt/kitchen_sensor/availability"] == ({"state": "online"}, True)
    assert messages["zigbee2mqtt/kitchen_sensor"][0]["last_seen"] == now.isoformat()
    assert messages["zigbee2mqtt/kitchen_sensor"][1] is False


def test_retained_value_is_published_by_a_client_that_then_disconnects():
    client = RecordingClient()
    now = datetime(2026, 8, 29, 10, 0, tzinfo=UTC)

    with (
        patch.object(publisher, "new_client", return_value=client),
        patch.object(publisher, "connect") as connect,
    ):
        publisher.publish_disconnected_retained_value("broker", 1883, now)

    connect.assert_called_once_with(client, "broker", 1883)
    topic, payload, qos, retain = client.messages[0]
    assert topic == "zigbee2mqtt/basement_freezer"
    assert payload == {
        "last_seen": "2026-08-29T10:00:00+00:00",
        "temperature": -18.7,
    }
    assert qos == 1
    assert retain is True
    assert [message[0] for message in client.messages[-2:]] == [
        "disconnect",
        "loop_stop",
    ]


def test_documented_scenario_table_is_generated_from_publisher_catalog():
    readme = (
        Path(__file__).parents[1] / "demo" / "zigbee2mqtt_scenario" / "README.md"
    ).read_text(encoding="utf-8")
    documented = readme.split("<!-- scenario-table:start -->\n", 1)[1].split(
        "\n<!-- scenario-table:end -->", 1
    )[0]

    assert documented == publisher.render_scenario_table()
