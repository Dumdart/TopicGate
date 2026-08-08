import asyncio

from topicgate.infrastructure.mqtt.mqtt_callbacks import MqttCallbacks


def test_mqtt_v5_unsubscribe_callback_accepts_reason_codes():
    asyncio.run(
        MqttCallbacks.on_unsubscribe(
            object(),
            object(),
            None,
            1,
            object(),
            [],
        )
    )
