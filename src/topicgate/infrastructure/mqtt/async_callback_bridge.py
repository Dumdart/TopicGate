import asyncio
import inspect
from collections import deque
from collections.abc import Callable
from threading import Lock
from typing import Any

from topicgate.core.payload_limits import (
    MAX_MESSAGE_CALLBACK_BATCH,
    MAX_PENDING_INGRESS_MESSAGES,
)

Callback = Callable[..., Any]


class AsyncCallbackBridge:
    """Admit callbacks from another thread and drain them on an asyncio loop."""

    def __init__(
        self,
        max_pending: int = MAX_PENDING_INGRESS_MESSAGES,
        batch_size: int = MAX_MESSAGE_CALLBACK_BATCH,
    ) -> None:
        self._max_pending = max_pending
        self._batch_size = batch_size
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pending: deque[tuple[Callback, tuple[Any, ...]]] = deque()
        self._lock = Lock()
        self._drain_scheduled = False
        self._drain_task: asyncio.Task[None] | None = None
        self._dropped_count = 0

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped_count

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def record_drop(self, count: int = 1) -> None:
        with self._lock:
            self._dropped_count += count

    def enqueue(self, callback: Callback, *args: Any) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        should_schedule = False
        # Check and update admission state atomically with the producer thread.
        with self._lock:
            if len(self._pending) >= self._max_pending:
                self._pending.popleft()
                self._dropped_count += 1
            self._pending.append((callback, args))
            if not self._drain_scheduled:
                self._drain_scheduled = True
                should_schedule = True

        if should_schedule:
            try:
                loop.call_soon_threadsafe(self._start_drain)
            except RuntimeError:
                with self._lock:
                    self._dropped_count += len(self._pending)
                    self._pending.clear()
                    self._drain_scheduled = False

    def _start_drain(self) -> None:
        self._drain_task = asyncio.create_task(self._drain())

    async def _drain(self) -> None:
        processed = 0
        while True:
            with self._lock:
                if not self._pending:
                    self._drain_scheduled = False
                    self._drain_task = None
                    return
                callback, args = self._pending.popleft()

            try:
                result = callback(*args)
                if inspect.isawaitable(result):
                    await result
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                asyncio.get_running_loop().call_exception_handler(
                    {
                        "message": "MQTT message callback failed",
                        "exception": ex,
                    }
                )

            processed += 1
            if processed >= self._batch_size:
                processed = 0
                await asyncio.sleep(0)
