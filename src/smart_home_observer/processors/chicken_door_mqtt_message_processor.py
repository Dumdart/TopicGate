
from smart_home_observer.core.interfaces.mqtt_message_processor import MqttMessageProcessor
from smart_home_observer.core.models.chicken_door import ChickenDoor
from smart_home_observer.core.models.mqtt_message import MqttMessage


class ChickenDoorMqttMessageProcessor(MqttMessageProcessor[ChickenDoor]):
    def process(self, state: ChickenDoor, message: MqttMessage) -> None:
        payload = message.payload.decode("utf-8").strip()

        if message.topic.endswith("/command"):
            state.command = payload

        elif message.topic.endswith("/status"):
            state.status = payload

        elif message.topic.endswith("/status_code"):
            state.status_code = int(payload)

        elif message.topic.endswith("/fault"):
            state.fault = payload

        elif message.topic.endswith("/connected"):
            state.connected = payload.lower() in {"1", "true", "on"}

        elif message.topic.endswith("/battery"):
            state.battery = int(payload)

        elif message.topic.endswith("/light_level"):
            state.light_level = int(payload)
