import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.observer_model import TopicState
from smart_home_observer.gui.main_view_model import MainViewModel


class FakeObserverRepository:
    def __init__(self) -> None:
        self._states: dict[str, TopicState] = {}
        self._messages: asyncio.Queue[MqttMessage] = asyncio.Queue()

    def get_state(self, topic: str) -> TopicState | None:
        return self._states.get(topic)

    async def messages(self) -> AsyncIterator[MqttMessage]:
        while True:
            yield await self._messages.get()

    def publish(self, message: MqttMessage) -> None:
        self._states[message.topic] = TopicState(
            name=message.topic.rsplit("/", maxsplit=1)[-1],
            topic=message.topic,
            payload=message.payload,
            qos=message.qos,
            retain=message.retain,
            recieved_at=datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc),
        )
        self._messages.put_nowait(message)


def test_view_model_displays_and_refreshes_the_selected_topic_state() -> None:
    async def scenario() -> None:
        topic = "SmartHome/Huehnerstall/door/status"
        repository = FakeObserverRepository()
        view_model = MainViewModel(repository, topic)

        assert view_model.value == "Waiting for a message"

        await view_model.start()
        repository.publish(MqttMessage(topic, b"open", qos=1, retain=True))
        await asyncio.sleep(0)

        assert view_model.topic == topic
        assert view_model.value == "open"
        assert view_model.quality_of_service == "1"
        assert view_model.retained == "True"
        assert view_model.received_at == "2026-08-04T12:00:00+00:00"

        await view_model.stop()

    asyncio.run(scenario())
