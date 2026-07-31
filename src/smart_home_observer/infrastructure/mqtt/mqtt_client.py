import asyncio
import inspect
import ssl
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as paho

from ...core.config.mqtt_config import MqttConfig


Callback = Callable[..., Any]


class MqttClient:
    def __init__(self, config: MqttConfig):
        self.config = config
        self.client = paho.Client(client_id="", userdata=None, protocol=paho.MQTTv5)

        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected_event: asyncio.Event | None = None
        self._connected = False
        self._loop_started = False

        self._on_connect: Callback | None = None
        self._on_disconnect: Callback | None = None
        self._on_publish: Callback | None = None
        self._on_subscribe: Callback | None = None
        self._on_unsubscribe: Callback | None = None

        self.client.on_connect = self._paho_on_connect
        self.client.on_disconnect = self._paho_on_disconnect
        self.client.on_publish = self._paho_on_publish
        self.client.on_subscribe = self._paho_on_subscribe
        self.client.on_unsubscribe = self._paho_on_unsubscribe

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self, on_connect: Callback | None = None, timeout: float = 10.0):
        self._loop = asyncio.get_running_loop()
        self._on_connect = on_connect

        if self._connected:
            return
        if self._loop_started:
            await self.wait_connected(timeout)
            return

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

    async def disconnect(self, on_disconnect: Callback | None = None):
        self._on_disconnect = on_disconnect

        if self.client.is_connected():
            await asyncio.to_thread(self.client.disconnect)
        if self._loop_started:
            await asyncio.to_thread(self.client.loop_stop)
            self._loop_started = False

        self._connected = False
        if self._connected_event is not None:
            self._connected_event.clear()

    async def publish(
        self,
        topic: str,
        payload: Any,
        retain: bool = False,
        on_publish: Callback | None = None,
    ) -> int:
        await self.wait_connected()
        self._on_publish = on_publish

        result = self.client.publish(topic, payload, qos=1, retain=retain)
        self._check_result(result.rc, "publish")
        return result.mid

    async def subscribe(self, topic: str, on_subscribe: Callback | None = None) -> int:
        await self.wait_connected()
        self._on_subscribe = on_subscribe

        result, mid = self.client.subscribe(topic)
        self._check_result(result, "subscribe")
        return mid

    async def unsubscribe(
        self,
        topic: str,
        on_unsubscribe: Callback | None = None,
    ) -> int:
        await self.wait_connected()
        self._on_unsubscribe = on_unsubscribe

        result, mid = self.client.unsubscribe(topic)
        self._check_result(result, "unsubscribe")
        return mid

    def message_callback_add(self, topic: str, callback: Callback):
        def forward(client: Any, userdata: Any, message: Any):
            self._call_on_loop(self._run_callback, callback, client, userdata, message)

        self.client.message_callback_add(topic, forward)

    def _configure(self):
        if self.config.use_tls:
            self.client.tls_set(tls_version=ssl.PROTOCOL_TLS)
        if self.config.username or self.config.password:
            self.client.username_pw_set(
                self.config.username or None,
                self.config.password or None,
            )

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
        self._run_callback(self._on_connect, client, userdata, flags, reason_code, properties)

    def _paho_on_disconnect(
        self,
        client,
        userdata,
        reason_code,
        properties=None,
    ):
        self._call_on_loop(
            self._handle_disconnect,
            client,
            userdata,
            None,
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

    def _paho_on_publish(self, client, userdata, mid, reason_code=None, properties=None):
        self._call_on_loop(
            self._run_callback,
            self._on_publish,
            client,
            userdata,
            mid,
            reason_code,
            properties,
        )

    def _paho_on_subscribe(self, client, userdata, mid, granted_qos, properties=None):
        self._call_on_loop(
            self._run_callback,
            self._on_subscribe,
            client,
            userdata,
            mid,
            granted_qos,
            properties,
        )

    def _paho_on_unsubscribe(
        self,
        client,
        userdata,
        mid,
        properties=None,
        reason_codes=None,
    ):
        self._call_on_loop(
            self._run_callback,
            self._on_unsubscribe,
            client,
            userdata,
            mid,
            properties,
            reason_codes,
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
            raise RuntimeError(f"Failed to {operation} MQTT: {paho.error_string(result)}")
