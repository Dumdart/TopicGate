from abc import ABC, abstractmethod
from typing import Any


class MqttCallbacks(ABC):
    @abstractmethod
    async def on_subscribe(
        self, client: Any, userdata: Any, mid: int, granted_qos: Any, properties: Any = None
    ) -> None:
        pass

    @abstractmethod
    async def on_connect(
        self, client: Any, userdata: Any, flags: Any, rc: Any, properties: Any = None
    ) -> None:
        pass

    @abstractmethod
    async def on_disconnect(
        self,
        client: Any,
        userdata: Any,
        disconnect_flags: Any,
        reason_code: Any = None,
        properties: Any = None,
    ) -> None:
        pass

    @abstractmethod
    async def on_publish(
        self,
        client: Any,
        userdata: Any,
        mid: int,
        reason_code: Any = None,
        properties: Any = None,
    ) -> None:
        pass

    @abstractmethod
    async def on_unsubscribe(
        self,
        client: Any,
        userdata: Any,
        mid: int,
        properties: Any = None,
        reason_codes: Any = None,
    ) -> None:
        pass

    @abstractmethod
    async def on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        pass
