from __future__ import annotations

import asyncio

from ... import db
from ...config import settings
from ...llm.limiter import LlmCallLimiter
from ..framework import load_run, run_eval, save_run
from .arms import full_rag_arm, linkedin_judge, no_rag_arm
from .cases import load_cases


async def main() -> None:
    # run_eval(both arms) -> EvalRun -> save_run() -> run_id -> load_run(run_id);
    # then report delta paired by case, segmented by regime, per metric.
    raise NotImplementedError


if __name__ == "__main__":
    asyncio.run(main())
