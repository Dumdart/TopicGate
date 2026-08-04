from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.interfaces.mqtt_repository import MqttRepository
from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.observer_model import (
    ObserverModel,
    TopicState,
)
from smart_home_observer.infrastructure.mqtt.callbacks.basic_callbacks import (
    BasicCallbacks,
)
from smart_home_observer.infrastructure.mqtt.mqtt_gate import MqttGate
from smart_home_observer.processors.observer_model_mqtt_message_processor import (
    ObserverModelMqttMessageProcessor,
)
from smart_home_observer.services.observer_model_service import ObserverModelService


class ObserverRepository(MqttRepository[ObserverModel]):
    """Observe messages matching the supplied absolute MQTT topic filters."""

    def __init__(self, config: MqttConfig, topic_filters: list[str]) -> None:
        self._state = ObserverModel(root_stats=[])
        self._mqtt_gate = MqttGate(config, BasicCallbacks(), topic_filters)
        self._message_processor = ObserverModelMqttMessageProcessor()
        self.message_queue: asyncio.Queue[MqttMessage] = asyncio.Queue()

    async def start(self) -> None:
        try:
            await self._mqtt_gate.start()
            await self._mqtt_gate.subscribe(self.handle_message)
        except Exception as ex:
            await self._mqtt_gate.stop()
            raise ConnectionError(
                "ObserverRepository could not start the MQTT connection."
            ) from ex

    async def stop(self) -> None:
        try:
            try:
                await self._mqtt_gate.unsubscribe()
            finally:
                await self._mqtt_gate.stop()
        except Exception as ex:
            raise ConnectionError(
                "ObserverRepository could not stop the MQTT connection."
            ) from ex

    def get(self) -> ObserverModel:
        return ObserverModelService.deep_copy(self._state)

    def get_value(self, topic: str) -> bytes | None:
        state = self.get_state(topic)
        if state:
            return state.payload
        return None

    def get_state(self, topic: str) -> TopicState | None:
        return self._state.topic_states.get(topic)

    def handle_message(self, _client, _userdata, msg: MqttMessage) -> None:
        self._message_processor.process(self._state, msg)
        self.message_queue.put_nowait(msg)
import asyncio
