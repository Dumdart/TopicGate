import json
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

    publisher.publish_initial_state(client)

    messages = {
        topic: (payload, retain) for topic, payload, _, retain in client.messages
    }
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
    assert messages["zigbee2mqtt/garage_sensor/availability"][0] == {
        "state": "offline"
    }
    assert (
        messages["zigbee2mqtt/attic_sensor"][0]["last_seen"]
        == publisher.STALE_LAST_SEEN
    )


def test_healthy_device_refreshes_with_non_retained_state():
    client = RecordingClient()

    publisher.publish_healthy_state(client)

    messages = {
        topic: (payload, retain) for topic, payload, _, retain in client.messages
    }
    assert messages["zigbee2mqtt/kitchen_sensor/availability"] == (
        {"state": "online"},
        True,
    )
    assert messages["zigbee2mqtt/kitchen_sensor"][0] == {
        "battery": 96,
        "humidity": 45.2,
        "linkquality": 132,
        "temperature": 21.3,
    }
    assert messages["zigbee2mqtt/kitchen_sensor"][1] is False


def test_retained_value_is_published_by_a_client_that_then_disconnects():
    client = RecordingClient()

    with (
        patch.object(publisher, "new_client", return_value=client),
        patch.object(publisher, "connect") as connect,
    ):
        publisher.publish_disconnected_retained_value("broker", 1883)

    connect.assert_called_once_with(client, "broker", 1883)
    topic, payload, qos, retain = client.messages[0]
    assert topic == "zigbee2mqtt/basement_freezer"
    assert payload == {"temperature": -18.7}
    assert qos == 1
    assert retain is True
    assert [message[0] for message in client.messages[-2:]] == [
        "disconnect",
        "loop_stop",
    ]


def test_healthy_phase_publishes_no_stale_or_disconnected_values():
    client = RecordingClient()

    publisher.publish_healthy_state(client)

    assert {message[0] for message in client.messages} == {
        "zigbee2mqtt/kitchen_sensor/availability",
        "zigbee2mqtt/kitchen_sensor",
    }


def test_documented_scenario_table_is_generated_from_publisher_catalog():
    readme = (
        Path(__file__).parents[1] / "demo" / "zigbee2mqtt_scenario" / "README.md"
    ).read_text(encoding="utf-8")
    documented = readme.split("<!-- scenario-table:start -->\n", 1)[1].split(
        "\n<!-- scenario-table:end -->", 1
    )[0]

    assert documented == publisher.render_scenario_table()
