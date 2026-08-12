from topicgate.infrastructure.mqtt.mqtt_callbacks import MqttCallbacks


async def test_mqtt_v5_unsubscribe_callback_accepts_reason_codes():
    await MqttCallbacks.on_unsubscribe(
        object(),
        object(),
        None,
        1,
        [],
        object(),
    )
