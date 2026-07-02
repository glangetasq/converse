from __future__ import annotations

import asyncio


class LlmCallLimiter:
    def __init__(self, concurrency: int, max_calls_per_minute: int | None = None) -> None:
        if not isinstance(concurrency, int) or isinstance(concurrency, bool):
            raise TypeError("concurrency must be an integer")
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")

        self.semaphore = asyncio.Semaphore(concurrency)
        self.min_interval_seconds = (
            60 / max_calls_per_minute if max_calls_per_minute is not None and max_calls_per_minute > 0 else 0
        )
        self._pace_lock = asyncio.Lock()
        self._next_call_at = 0.0

    async def __aenter__(self) -> "LlmCallLimiter":
        await self.wait_for_turn()
        await self.semaphore.acquire()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        self.semaphore.release()

    async def wait_for_turn(self) -> None:
        if self.min_interval_seconds <= 0:
            return

        loop = asyncio.get_running_loop()
        async with self._pace_lock:
            now = loop.time()
            wait_seconds = self._next_call_at - now
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
                now = loop.time()

            self._next_call_at = now + self.min_interval_seconds
