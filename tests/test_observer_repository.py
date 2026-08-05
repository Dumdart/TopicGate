import asyncio
from unittest.mock import patch

from paho.mqtt.reasoncodes import ReasonCode

from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.infrastructure.repository.observer_repository import (
    ConnectionStatus,
    ObserverRepository,
)


class FakePahoClient:
    def __init__(self, **kwargs) -> None:
        self.events: list[tuple] = []
        self.connected = False
        self.on_connect = None
        self.on_disconnect = None
        self.on_publish = None
        self.on_subscribe = None
        self.on_unsubscribe = None

    def connect(self, host: str, port: int) -> int:
        self.connected = True
        return 0

    def loop_start(self) -> int:
        self.on_connect(self, None, {}, ReasonCode(2, identifier=0), None)
        return 0

    def loop_stop(self) -> None:
        self.events.append(("loop_stop",))

    def is_connected(self) -> bool:
        return self.connected

    def disconnect(self) -> int:
        self.connected = False
        self.on_disconnect(self, None, 0, None)
        return 0

    def subscribe(self, topics: list[tuple[str, object]]) -> tuple[int, int]:
        self.events.append(("subscribe", topics))
        self.on_subscribe(self, None, 1, [1], None)
        return 0, 1

    def unsubscribe(self, topics: list[str]) -> tuple[int, int]:
        self.events.append(("unsubscribe", topics))
        self.on_unsubscribe(self, None, 1, None, [1])
        return 0, 1

    def message_callback_add(self, topic: str, callback: object) -> None:
        self.events.append(("message_callback_add", topic))

    def message_callback_remove(self, topic: str) -> None:
        self.events.append(("message_callback_remove", topic))

    def tls_set(self, **kwargs) -> None:
        pass

    def username_pw_set(self, username: str | None, password: str | None) -> None:
        pass


def test_repository_returns_state_and_value_by_topic_path() -> None:
    repository = ObserverRepository(
        MqttConfig(host="broker", port=1883, username="", password=""),
        ["SmartHome/#"],
    )
    message = MqttMessage(
        "SmartHome/Huehnerstall/door/status", b"open", qos=1, retain=True
    )

    repository.handle_message(None, None, message)

    state = repository.get_state(message.topic)

    assert state is not None
    assert state.topic == message.topic
    assert repository.get_value(message.topic) == b"open"
    assert repository.get_state("SmartHome/Huehnerstall/door/missing") is None
    assert repository.get_value("SmartHome/missing") is None


def test_repository_updates_topic_state_before_publishing_message() -> None:
    async def scenario() -> None:
        repository = ObserverRepository(
            MqttConfig(host="broker", port=1883, username="", password=""),
            ["SmartHome/#"],
        )
        message = MqttMessage(
            "SmartHome/discovered/value", b"42", qos=0, retain=False
        )
        stream = repository.messages()

        repository.handle_message(None, None, message)

        assert repository.get_value(message.topic) == b"42"
        assert await anext(stream) == message
        await stream.aclose()

    asyncio.run(scenario())


def test_repository_subscribes_to_its_configured_absolute_topic_filters() -> None:
    topic_filters = ["/SmartHome/Huehnerstall/door/#", "SmartHome/+/status"]
    repository = ObserverRepository(
        MqttConfig(host="broker", port=1883, username="", password=""),
        topic_filters,
    )

    assert repository._mqtt_gate.topics == topic_filters


def test_connection_loss_reconnects_and_restores_subscriptions() -> None:
    async def scenario() -> None:
        topic_filters = ["/SmartHome/#", "SmartHome/+/status"]
        with patch(
            "smart_home_observer.infrastructure.mqtt.mqtt_client.paho.Client",
            FakePahoClient,
        ):
            repository = ObserverRepository(
                MqttConfig(host="broker", port=1883, username="", password=""),
                topic_filters,
            )
            status_stream = repository.connection_statuses()
            await repository.start()
            fake_client = repository._mqtt_gate.client.client
            await asyncio.sleep(0)

            assert repository.connection_status == ConnectionStatus.CONNECTED
            assert await anext(status_stream) == ConnectionStatus.CONNECTING
            assert await anext(status_stream) == ConnectionStatus.CONNECTED
            assert len(
                [event for event in fake_client.events if event[0] == "subscribe"]
            ) == 1

            fake_client.connected = False
            fake_client.on_disconnect(fake_client, None, "network", None)
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert repository.connection_status == ConnectionStatus.RECONNECTING
            assert await anext(status_stream) == ConnectionStatus.RECONNECTING

            fake_client.connected = True
            fake_client.on_connect(
                fake_client, None, {}, ReasonCode(2, identifier=0), None
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            subscriptions = [
                event for event in fake_client.events if event[0] == "subscribe"
            ]
            assert repository.connection_status == ConnectionStatus.CONNECTED
            assert await anext(status_stream) == ConnectionStatus.CONNECTED
            assert len(subscriptions) == 2
            assert [topic for topic, _ in subscriptions[-1][1]] == topic_filters

            await repository.stop()
            assert await anext(status_stream) == ConnectionStatus.DISCONNECTED
            await repository.stop()
            await status_stream.aclose()
            assert [
                event[1]
                for event in fake_client.events
                if event[0] == "message_callback_remove"
            ] == topic_filters

    asyncio.run(scenario())


def test_startup_failure_leaves_repository_disconnected() -> None:
    async def scenario() -> None:
        repository = ObserverRepository(
            MqttConfig(host="broker", port=1883, username="", password=""),
            ["SmartHome/#"],
        )

        async def fail_start() -> None:
            raise RuntimeError("broker unavailable")

        async def stop_gate() -> None:
            return None

        repository._mqtt_gate.start = fail_start
        repository._mqtt_gate.stop = stop_gate

        try:
            await repository.start()
        except ConnectionError:
            pass
        else:
            raise AssertionError("Expected startup to fail")

        assert repository.connection_status == ConnectionStatus.DISCONNECTED

    asyncio.run(scenario())


def test_updating_a_subscription_replaces_the_active_broker_filter() -> None:
    async def scenario() -> None:
        with patch(
            "smart_home_observer.infrastructure.mqtt.mqtt_client.paho.Client",
            FakePahoClient,
        ):
            repository = ObserverRepository(
                MqttConfig(host="broker", port=1883, username="", password=""),
                ["SmartHome/old/#"],
            )
            await repository.start()
            fake_client = repository._mqtt_gate.client.client

            await repository.update_subscription(
                "SmartHome/old/#",
                Subscription(
                    "SmartHome/new/#",
                    qos=2,
                    retain_as_published=True,
                    retain_handling=1,
                ),
            )

            assert repository.subscriptions == (
                Subscription(
                    "SmartHome/new/#",
                    qos=2,
                    retain_as_published=True,
                    retain_handling=1,
                ),
            )
            assert [
                event[1] for event in fake_client.events if event[0] == "unsubscribe"
            ] == [["SmartHome/old/#"]]
            assert [
                topic
                for topic, _ in [
                    event for event in fake_client.events if event[0] == "subscribe"
                ][-1][1]
            ] == ["SmartHome/new/#"]
            await repository.stop()

    asyncio.run(scenario())
