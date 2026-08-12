import asyncio
import inspect
import ssl
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as paho
from paho.mqtt.subscribeoptions import SubscribeOptions

from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.core.models.subscription import Subscription
from topicgate.core.mqtt_topics import validate_topic_name
from topicgate.core.payload_limits import (
    MAX_STORED_PAYLOAD_BYTES,
)

from ...core.config.mqtt_config import MqttConfig
from .async_callback_bridge import AsyncCallbackBridge

Callback = Callable[..., Any]


class MqttClient:
    def __init__(self, config: MqttConfig, qos: int = 1):
        self.config = config
        self.client = paho.Client(
            callback_api_version=paho.CallbackAPIVersion.VERSION2,
            client_id="",
            userdata=None,
            protocol=paho.MQTTv5,
        )

        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected_event: asyncio.Event | None = None
        self._connected = False
        self._loop_started = False
        self._configured = False
        self._callback_bridge = AsyncCallbackBridge()

        self._on_connect: Callback | None = None
        self._on_disconnect: Callback | None = None
        self._on_publish: Callback | None = None
        self._on_subscribe: Callback | None = None
        self._on_unsubscribe: Callback | None = None

        self.qos = qos

        self.client.on_connect = self._paho_on_connect
        self.client.on_disconnect = self._paho_on_disconnect
        self.client.on_publish = self._paho_on_publish
        self.client.on_subscribe = self._paho_on_subscribe
        self.client.on_unsubscribe = self._paho_on_unsubscribe

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def dropped_message_count(self) -> int:
        return self._callback_bridge.dropped_count

    async def connect(
        self,
        on_connect: Callback | None = None,
        timeout: float = 10.0,
        *,
        on_disconnect: Callback | None = None,
    ) -> bool:
        self._loop = asyncio.get_running_loop()
        self._callback_bridge.bind_loop(self._loop)
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

        if self._connected:
            return True
        if self._loop_started:
            await self.wait_connected(timeout)
            return True

        self._connected_event = asyncio.Event()
        self._configure()

        result = await asyncio.to_thread(
            self.client.connect,
            self.config.host,
            self.config.port,
        )
        self._check_result(result, "connect")

        self._check_result(self.client.loop_start(), "start MQTT network loop")
        self._loop_started = True

        try:
            await asyncio.wait_for(self._connected_event.wait(), timeout)
        except BaseException:
            await self.disconnect()
            raise
        if not self._connected:
            await self.disconnect()
            raise ConnectionError("MQTT broker rejected the connection")

        return self.is_connected

    async def wait_connected(self, timeout: float | None = None):
        if self._connected:
            return
        if self._connected_event is None:
            raise RuntimeError("MqttClient.connect() must be called first")

        wait = self._connected_event.wait()
        if timeout is None:
            await wait
        else:
            await asyncio.wait_for(wait, timeout)

        if not self._connected:
            raise ConnectionError("MQTT client is not connected")

    async def disconnect(self, on_disconnect: Callback | None = None) -> bool:
        self._on_disconnect = on_disconnect

        if self.client.is_connected():
            await asyncio.to_thread(self.client.disconnect)
        if self._loop_started:
            await asyncio.to_thread(self.client.loop_stop)
            self._loop_started = False

        self._connected = False
        if self._connected_event is not None:
            self._connected_event.clear()

        return self.is_connected

    async def subscribe(
        self, topic: str, on_subscribe: Callback | None = None
    ) -> int | None:
        await self.wait_connected()
        self._on_subscribe = on_subscribe

        result, mid = self.client.subscribe((topic, SubscribeOptions(qos=self.qos)))
        self._check_result(result, "subscribe")
        return mid

    async def subscribe_multiple(
        self,
        subscriptions: list[Subscription] | list[str],
        on_subscribe: Callback | None = None,
    ) -> int | None:
        await self.wait_connected()
        self._on_subscribe = on_subscribe
        normalized_subscriptions = [
            item if isinstance(item, Subscription) else Subscription(item)
            for item in subscriptions
        ]

        result, mid = self.client.subscribe(
            [
                (
                    subscription.topic_filter,
                    SubscribeOptions(
                        qos=subscription.qos,
                        retainAsPublished=subscription.retain_as_published,
                        retainHandling=subscription.retain_handling,
                    ),
                )
                for subscription in normalized_subscriptions
            ]
        )
        self._check_result(result, "subscribe")
        return mid

    async def unsubscribe(
        self,
        topic: str,
        on_unsubscribe: Callback | None = None,
    ) -> int | None:
        await self.wait_connected()
        self._on_unsubscribe = on_unsubscribe

        result, mid = self.client.unsubscribe(topic)
        self._check_result(result, "unsubscribe")
        return mid

    async def unsubscribe_multiple(
        self,
        topics: list[str],
        on_unsubscribe: Callback | None = None,
    ) -> int | None:
        await self.wait_connected()
        self._on_unsubscribe = on_unsubscribe

        result, mid = self.client.unsubscribe([topic for topic in topics])
        self._check_result(result, "unsubscribe")
        return mid

    async def publish(self, topic: str, payload: bytes) -> None:
        await self.wait_connected()
        validate_topic_name(topic)
        result = await asyncio.to_thread(
            self.client.publish,
            topic,
            payload,
            self.qos,
        )
        self._check_result(result.rc, "publish")

    def message_callback_add(self, topic: str, callback: Callback):
        def forward(client: Any, userdata: Any, message: Any):
            topic = str(message.topic)
            try:
                validate_topic_name(topic)
            except ValueError:
                self._callback_bridge.record_drop()
                return
            payload_size = len(message.payload)
            mqtt_message = MqttMessage(
                topic=topic,
                payload=bytes(message.payload[:MAX_STORED_PAYLOAD_BYTES]),
                qos=int(message.qos),
                retain=bool(message.retain),
                payload_size=payload_size,
            )
            self._callback_bridge.enqueue(callback, client, userdata, mqtt_message)

        self.client.message_callback_add(topic, forward)

    def message_callback_remove(self, topic: str) -> None:
        self.client.message_callback_remove(topic)

    def _configure(self) -> None:
        if self._configured:
            return
        if self.config.use_tls:
            self.client.tls_set(tls_version=ssl.PROTOCOL_TLS)
        if self.config.username or self.config.password:
            self.client.username_pw_set(
                self.config.username or None,
                self.config.password or None,
            )
        # Check that TLS is configured only once: Paho rejects a second
        # tls_set call on the same client during a manual reconnect.
        self._configured = True

    def _paho_on_connect(self, client, userdata, flags, reason_code, properties=None):
        self._call_on_loop(
            self._handle_connect,
            client,
            userdata,
            flags,
            reason_code,
            properties,
        )

    def _handle_connect(self, client, userdata, flags, reason_code, properties):
        self._connected = reason_code == 0
        if self._connected_event is not None:
            self._connected_event.set()
        self._run_callback(
            self._on_connect, client, userdata, flags, reason_code, properties
        )

    def _paho_on_disconnect(
        self,
        client,
        userdata,
        disconnect_flags,
        reason_code,
        properties,
    ):
        self._call_on_loop(
            self._handle_disconnect,
            client,
            userdata,
            disconnect_flags,
            reason_code,
            properties,
        )

    def _handle_disconnect(
        self,
        client,
        userdata,
        disconnect_flags,
        reason_code,
        properties,
    ):
        self._connected = False
        if self._connected_event is not None:
            self._connected_event.clear()
        self._run_callback(
            self._on_disconnect,
            client,
            userdata,
            disconnect_flags,
            reason_code,
            properties,
        )

    def _paho_on_publish(self, client, userdata, mid, reason_code, properties):
        self._call_on_loop(
            self._run_callback,
            self._on_publish,
            client,
            userdata,
            mid,
            reason_code,
            properties,
        )

    def _paho_on_subscribe(self, client, userdata, mid, reason_codes, properties):
        self._call_on_loop(
            self._run_callback,
            self._on_subscribe,
            client,
            userdata,
            mid,
            reason_codes,
            properties,
        )

    def _paho_on_unsubscribe(
        self,
        client,
        userdata,
        mid,
        reason_codes,
        properties,
    ):
        self._call_on_loop(
            self._run_callback,
            self._on_unsubscribe,
            client,
            userdata,
            mid,
            reason_codes,
            properties,
        )

    def _call_on_loop(self, callback: Callback, *args):
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(callback, *args)

    @staticmethod
    def _run_callback(callback: Callback | None, *args):
        if callback is None:
            return
        result = callback(*args)
        if inspect.isawaitable(result):
            asyncio.create_task(result)

    @staticmethod
    def _check_result(result, operation: str):
        if result != paho.MQTT_ERR_SUCCESS:
            raise RuntimeError(
                f"Failed to {operation} MQTT: {paho.error_string(result)}"
            )
