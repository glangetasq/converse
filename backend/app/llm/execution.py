from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from .limiter import LlmCallLimiter


@dataclass(frozen=True)
class LlmExecutionStrategy:
    concurrency: int | None = None
    max_calls_per_minute: int | None = None
    batch: bool = False

    @cached_property
    def limiter(self) -> LlmCallLimiter | None:
        # cached so every call shares one limiter — the concurrency cap and pacing only bind if they do
        if self.batch or self.concurrency is None:
            return None
        return LlmCallLimiter(self.concurrency, self.max_calls_per_minute)


ONLINE = LlmExecutionStrategy()
