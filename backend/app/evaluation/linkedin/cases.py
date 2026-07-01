from __future__ import annotations

from ..framework.core import Case

EARLY_MAX_DEPTH = 2
DEEP_MIN_DEPTH = 5


def depth_regime(thread_len: int) -> str:
    raise NotImplementedError


async def load_cases() -> list[Case]:
    # eval_examples -> Cases; attach regime + ids + quality onto meta.
    raise NotImplementedError
