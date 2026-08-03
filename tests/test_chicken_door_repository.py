import asyncio
from unittest.mock import AsyncMock

from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.infrastructure.repository.chicken_door_repository import (
    ChickenDoorRepository,
)


def config() -> MqttConfig:
    return MqttConfig(
        host="broker",
        port=1883,
        username="",
        password="",
        base_topic="home",
    )


def test_repository_starts_and_stops_its_mqtt_gate() -> None:
    async def scenario() -> None:
        repository = ChickenDoorRepository(config())
        repository._mqtt_gate.start = AsyncMock()
        repository._mqtt_gate.subscribe = AsyncMock()
        repository._mqtt_gate.stop = AsyncMock()

        await repository.start()
        await repository.stop()

        repository._mqtt_gate.start.assert_awaited_once_with()
        repository._mqtt_gate.subscribe.assert_awaited_once_with(repository.handle_message)
        repository._mqtt_gate.stop.assert_awaited_once_with()

    asyncio.run(scenario())


def test_repository_processes_messages_into_its_current_state() -> None:
    repository = ChickenDoorRepository(config())

    repository.handle_message(None, None, MqttMessage("home/status", b"open", 1, False))
    repository.handle_message(None, None, MqttMessage("home/battery", b"84", 1, False))

    assert repository.get().status == "open"
    assert repository.get().battery == 84


def test_repository_declares_all_chicken_door_topics() -> None:
    assert ChickenDoorRepository.get_mqtt_topics() == [
        "command",
        "status",
        "status_code",
        "fault",
        "connected",
        "battery",
        "light_level",
    ]
