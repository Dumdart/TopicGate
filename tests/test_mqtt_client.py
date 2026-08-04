import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from paho.mqtt.reasoncodes import ReasonCode

from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.infrastructure.mqtt.mqtt_client import MqttClient
from smart_home_observer.infrastructure.mqtt.mqtt_gate import MqttGate
from smart_home_observer.infrastructure.mqtt.mqtt_callbacks import MqttCallbacks


class FakePahoClient:
    instances = []

    def __init__(self, **kwargs):
        self.events = []
        self.connected = False
        self.on_connect = None
        self.on_disconnect = None
        self.on_publish = None
        self.on_subscribe = None
        self.on_unsubscribe = None
        self.message_callback = None
        FakePahoClient.instances.append(self)

    def connect(self, host, port):
        self.events.append(("connect", host, port))
        self.connected = True
        return 0

    def loop_start(self):
        self.events.append(("loop_start",))
        self.on_connect(self, None, {}, ReasonCode(2, identifier=0), None)
        return 0

    def loop_stop(self):
        self.events.append(("loop_stop",))

    def is_connected(self):
        return self.connected

    def disconnect(self):
        self.events.append(("disconnect",))
        self.connected = False
        self.on_disconnect(self, None, 0, None)
        return 0

    def subscribe(self, topic):
        self.events.append(("subscribe", topic))
        self.on_subscribe(self, None, 12, [1], None)
        return 0, 12

    def unsubscribe(self, topic):
        self.events.append(("unsubscribe", topic))
        self.on_unsubscribe(self, None, 13, "properties", ["success"])
        return 0, 13

    def message_callback_add(self, topic, callback):
        self.events.append(("message_callback_add", topic))
        self.message_callback = callback

    def message_callback_remove(self, topic):
        self.events.append(("message_callback_remove", topic))

    def tls_set(self, **kwargs):
        self.events.append(("tls_set", kwargs))

    def username_pw_set(self, username, password):
        self.events.append(("username_pw_set", username, password))


class TestCallbacks(MqttCallbacks):
    async def on_subscribe(self, client, userdata, mid, granted_qos, properties=None):
        pass

    async def on_connect(self, client, userdata, flags, rc, properties=None):
        pass

    async def on_disconnect(
        self, client, userdata, disconnect_flags, reason_code=None, properties=None
    ):
        pass

    async def on_publish(self, client, userdata, mid, reason_code=None, properties=None):
        pass

    async def on_unsubscribe(
        self, client, userdata, mid, properties=None, reason_codes=None
    ):
        pass

    async def on_message(self, client, userdata, msg):
        pass


def config():
    return MqttConfig(
        host="broker",
        port=1883,
        username="",
        password="",
    )


def test_async_gate_registers_message_callback_before_subscribing():
    async def scenario():
        FakePahoClient.instances.clear()
        with patch("smart_home_observer.infrastructure.mqtt.mqtt_client.paho.Client", FakePahoClient):
            gate = MqttGate(config(), TestCallbacks(), ["SmartHome/door/status"])
            await gate.start(timeout=1)
            await gate.subscribe()
            events = [event[0] for event in FakePahoClient.instances[0].events]
            assert events.index("message_callback_add") < events.index("subscribe")
            await gate.stop()

    asyncio.run(scenario())


def test_async_gate_subscribes_all_configured_topics_with_custom_callback():
    async def scenario():
        FakePahoClient.instances.clear()

        async def on_message(client, userdata, message):
            pass

        with patch("smart_home_observer.infrastructure.mqtt.mqtt_client.paho.Client", FakePahoClient):
            gate = MqttGate(
                config(),
                TestCallbacks(),
                ["SmartHome/door/status", "/SmartHome/door/battery/"],
            )
            await gate.start(timeout=1)

            assert gate.is_started
            assert await gate.subscribe(on_message) == 12
            fake_client = FakePahoClient.instances[-1]
            callback_topics = [
                event[1]
                for event in fake_client.events
                if event[0] == "message_callback_add"
            ]
            subscription = next(event for event in fake_client.events if event[0] == "subscribe")

            assert callback_topics == ["SmartHome/door/status", "/SmartHome/door/battery/"]
            assert [topic for topic, _ in subscription[1]] == callback_topics

            assert await gate.unsubscribe() == 13
            await gate.stop()
            assert not gate.is_started

    asyncio.run(scenario())


def test_mqtt_gate_has_no_topics_when_none_are_configured():
    gate = MqttGate(config(), TestCallbacks())

    assert gate.topics == []


def test_async_unsubscribe_preserves_mqtt_v5_callback_argument_order():
    async def scenario():
        received = asyncio.Event()
        values = []

        async def on_unsubscribe(client, userdata, mid, properties, reason_codes):
            values.extend((mid, properties, reason_codes))
            received.set()

        with patch("smart_home_observer.infrastructure.mqtt.mqtt_client.paho.Client", FakePahoClient):
            client = MqttClient(config())
            await client.connect(timeout=1)
            await client.unsubscribe("SmartHome/door/status", on_unsubscribe)
            await asyncio.wait_for(received.wait(), timeout=1)
            await client.disconnect()

        assert values == [13, "properties", ["success"]]

    asyncio.run(scenario())


def test_async_disconnect_normalizes_paho_v1_mqtt5_callback_arguments():
    async def scenario():
        received = asyncio.Event()
        values = []

        async def on_disconnect(
            client, userdata, disconnect_flags, reason_code, properties
        ):
            values.extend((disconnect_flags, reason_code, properties))
            received.set()

        with patch("smart_home_observer.infrastructure.mqtt.mqtt_client.paho.Client", FakePahoClient):
            client = MqttClient(config())
            await client.connect(timeout=1)
            client._on_disconnect = on_disconnect
            fake_client = FakePahoClient.instances[-1]
            fake_client.on_disconnect(fake_client, None, "reason", "properties")
            await asyncio.wait_for(received.wait(), timeout=1)
            await client.disconnect()

        assert values == [None, "reason", "properties"]

    asyncio.run(scenario())


def test_async_message_callback_is_awaited_on_application_loop():
    async def scenario():
        received = asyncio.Event()
        received_message = None

        async def on_message(client, userdata, message):
            nonlocal received_message
            received_message = message
            received.set()

        with patch("smart_home_observer.infrastructure.mqtt.mqtt_client.paho.Client", FakePahoClient):
            client = MqttClient(config())
            await client.connect(timeout=1)
            client.message_callback_add("SmartHome/door/status", on_message)
            fake_client = FakePahoClient.instances[-1]
            paho_message = SimpleNamespace(
                topic="SmartHome/door/status", payload=b"on", qos=1, retain=False
            )
            fake_client.message_callback(fake_client, None, paho_message)
            await asyncio.wait_for(received.wait(), timeout=1)
            await client.disconnect()

        assert received_message == MqttMessage(
            topic="SmartHome/door/status", payload=b"on", qos=1, retain=False
        )

    asyncio.run(scenario())
