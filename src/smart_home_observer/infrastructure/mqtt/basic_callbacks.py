from typing import Any

from .mqtt_callbacks import MqttCallbacks


class BasicCallbacks(MqttCallbacks):
    async def on_subscribe(
        self,
        client: Any,
        userdata: Any,
        mid: int,
        granted_qos: Any,
        properties: Any = None,
    ) -> None:
        print(f"Subscribed: mid={mid}, granted_qos={granted_qos}")

    async def on_connect(
        self,
        client: Any,
        userdata: Any,
        flags: Any,
        rc: Any,
        properties: Any = None,
    ) -> None:
        print(f"Connected: reason_code={rc}")

    async def on_disconnect(
        self,
        client: Any,
        userdata: Any,
        disconnect_flags: Any,
        reason_code: Any = None,
        properties: Any = None,
    ) -> None:
        code = reason_code if reason_code is not None else disconnect_flags
        print(f"Disconnected: reason_code={code}")

    async def on_publish(
        self,
        client: Any,
        userdata: Any,
        mid: int,
        reason_code: Any = None,
        properties: Any = None,
    ) -> None:
        print(f"Published: mid={mid}, reason_code={reason_code}")

    async def on_unsubscribe(
        self,
        client: Any,
        userdata: Any,
        mid: int,
        properties: Any = None,
        reason_codes: Any = None,
    ) -> None:
        print(f"Unsubscribed: mid={mid}, reason_codes={reason_codes}")

    async def on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        print(f"Message: topic={msg.topic}, payload={msg.payload!r}")


BasicMqttCallbacks = BasicCallbacks
