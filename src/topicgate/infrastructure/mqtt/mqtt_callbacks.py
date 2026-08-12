from abc import ABC, abstractmethod
from typing import Any


class MqttCallbacks(ABC):
    @abstractmethod
    async def on_subscribe(
        self, client: Any, userdata: Any, mid: int, reason_codes: Any, properties: Any
    ) -> None:
        pass

    @abstractmethod
    async def on_connect(
        self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any
    ) -> None:
        pass

    @abstractmethod
    async def on_disconnect(
        self,
        client: Any,
        userdata: Any,
        disconnect_flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        pass

    @abstractmethod
    async def on_publish(
        self,
        client: Any,
        userdata: Any,
        mid: int,
        reason_code: Any,
        properties: Any,
    ) -> None:
        pass

    @abstractmethod
    async def on_unsubscribe(
        self,
        client: Any,
        userdata: Any,
        mid: int,
        reason_codes: Any,
        properties: Any,
    ) -> None:
        pass

    @abstractmethod
    async def on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        pass
