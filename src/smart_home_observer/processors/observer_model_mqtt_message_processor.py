from datetime import datetime, timezone

from smart_home_observer.core.interfaces.mqtt_message_processor import MqttMessageProcessor
from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.observer_model import ObserverModel, TopicState
from smart_home_observer.services.observer_model_service import ObserverModelService


class ObserverModelMqttMessageProcessor(MqttMessageProcessor[ObserverModel]):
    def process(self, state: ObserverModel, message: MqttMessage) -> None:
        node = ObserverModelService.find_node(state, message.topic)

        if node is not None:
            node.state = TopicState(
                name=node.segment,
                topic=message.topic,
                payload=message.payload,
                qos=message.qos,
                retain=message.retain,
                recieved_at=datetime.now(timezone.utc),
            )
