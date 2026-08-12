import asyncio
from unittest.mock import patch

from topicgate.infrastructure.mqtt.async_callback_bridge import AsyncCallbackBridge


async def test_bridge_executes_sync_and_async_callbacks_in_fifo_order() -> None:
    bridge = AsyncCallbackBridge()
    bridge.bind_loop(asyncio.get_running_loop())
    received: list[int] = []
    complete = asyncio.Event()

    def sync_callback(value: int) -> None:
        received.append(value)

    async def async_callback(value: int) -> None:
        await asyncio.sleep(0)
        received.append(value)
        complete.set()

    bridge.enqueue(sync_callback, 1)
    bridge.enqueue(async_callback, 2)

    await asyncio.wait_for(complete.wait(), timeout=1)

    assert received == [1, 2]


async def test_bridge_reports_failure_and_continues_draining() -> None:
    bridge = AsyncCallbackBridge()
    loop = asyncio.get_running_loop()
    bridge.bind_loop(loop)
    contexts: list[dict] = []
    complete = asyncio.Event()
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda unused_loop, context: contexts.append(context))

    def failing_callback() -> None:
        raise ValueError("bad message")

    try:
        bridge.enqueue(failing_callback)
        bridge.enqueue(complete.set)
        await asyncio.wait_for(complete.wait(), timeout=1)
    finally:
        loop.set_exception_handler(previous_handler)

    assert len(contexts) == 1
    assert contexts[0]["message"] == "MQTT message callback failed"
    assert isinstance(contexts[0]["exception"], ValueError)


async def test_bridge_yields_after_each_callback_batch() -> None:
    bridge = AsyncCallbackBridge(batch_size=2)
    bridge.bind_loop(asyncio.get_running_loop())
    received: list[int] = []
    complete = asyncio.Event()

    def callback(value: int) -> None:
        received.append(value)
        if value == 2:
            complete.set()

    with patch(
        "topicgate.infrastructure.mqtt.async_callback_bridge.asyncio.sleep",
        wraps=asyncio.sleep,
    ) as sleep:
        for value in range(3):
            bridge.enqueue(callback, value)
        await asyncio.wait_for(complete.wait(), timeout=1)

    assert received == [0, 1, 2]
    assert sleep.await_count == 1


def test_bridge_drops_queued_callback_when_loop_scheduling_fails() -> None:
    class RejectingLoop:
        def is_closed(self) -> bool:
            return False

        def call_soon_threadsafe(self, callback) -> None:
            raise RuntimeError("loop stopped")

    bridge = AsyncCallbackBridge()
    bridge.bind_loop(RejectingLoop())  # type: ignore[arg-type]

    bridge.enqueue(lambda: None)

    assert bridge.pending_count == 0
    assert bridge.dropped_count == 1
