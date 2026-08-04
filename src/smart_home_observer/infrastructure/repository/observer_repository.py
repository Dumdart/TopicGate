from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.interfaces.mqtt_repository import MqttRepository
from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.observer_model import (
    ObserverModel,
    TopicNode,
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
from smart_home_observer.services.topic_service import TopicService


class ObserverRepository(MqttRepository[ObserverModel]):
    def __init__(self, config: MqttConfig) -> None:
        self._state = TopicService.get_topics()
        self._mqtt_gate = MqttGate(
            config, BasicCallbacks(), ObserverModelService.get_all_topics(self._state)
        )

        self._message_processor = ObserverModelMqttMessageProcessor()

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

    def get_value(self, topic) -> bytes | None:
        state = self.get_state(topic)
        if state:
            return state.payload
        return None

    def get_state(self, topic) -> TopicState | None:
        segments = topic.split("/")
        if not segments:
            return None

        node = next(
            (root for root in self._state.root_stats if root.segment == segments[0]),
            None,
        )
        for segment in segments[1:]:
            if node is None:
                return None
            node = node.children.get(segment)

        return node.state if node is not None else None

    def handle_message(self, _client, _userdata, msg: MqttMessage) -> None:
        self._message_processor.process(self._state, msg)
        print(self._state)
