from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.interfaces.mqtt_repository import MqttRepository
from smart_home_observer.core.models.chicken_door import ChickenDoor
from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.observer_model import TopicState
from smart_home_observer.infrastructure.mqtt.callbacks.basic_callbacks import (
    BasicCallbacks,
)
from smart_home_observer.processors.chicken_door_mqtt_message_processor import (
    ChickenDoorMqttMessageProcessor,
)
from smart_home_observer.infrastructure.mqtt.mqtt_gate import MqttGate


class ChickenDoorRepository(MqttRepository[ChickenDoor]):
    def __init__(self, config: MqttConfig) -> None:
        self._mqtt_gate = MqttGate(
            config, BasicCallbacks(), ChickenDoorRepository.get_mqtt_topics()
        )
        self._message_processor = ChickenDoorMqttMessageProcessor()
        self._state = ChickenDoor("", "", -1, "", False, -1, -1)

    async def start(self) -> None:
        await self._mqtt_gate.start()
        await self._mqtt_gate.subscribe(self.handle_message)

    async def stop(self) -> None:
        await self._mqtt_gate.stop()

    def get(self) -> ChickenDoor:
        return ChickenDoor(
            self._state.command,
            self._state.status,
            self._state.status_code,
            self._state.fault,
            self._state.connected,
            self._state.battery,
            self._state.light_level,
        )

    def get_value(self, topic)  -> bytes | None:
        pass
    def get_state(self, topic) -> TopicState | None:
        pass

    def handle_message(self, _client, _userdata, msg: MqttMessage) -> None:
        self._message_processor.process(self._state, msg)

    @staticmethod
    def get_mqtt_topics() -> list[str]:
        return [
            "command",
            "status",
            "status_code",
            "fault",
            "connected",
            "battery",
            "light_level",
        ]
