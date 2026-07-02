"""Compose arms (+ optional judge) with the factory, run + persist one eval, return
(run_id, results). One arm -> pointwise, two -> pairwise; the judge matches that plan."""

from __future__ import annotations

import asyncio
from typing import Sequence

import pandas as pd

from ... import db
from ...config import settings
from ...llm import LlmCallLimiter
from ..framework import Arm, Case, Judge, load_run, run_eval, save_run
from ..framework.runner import infer_plan
from .cases import load_cases
from .factory import full_rag, no_rag
from .factory import judge as make_judge


async def run_linkedin_eval(
    arms: Sequence[Arm],
    judge: Judge | None = None,
    *,
    samples: int = 1,
    label: str | None = None,
    cases: Sequence[Case] | None = None,
    limiter: LlmCallLimiter | None = None,
) -> tuple[str, pd.DataFrame]:
    """`judge` defaults to a judge matching the arm count; `cases` to every
    non-intro LinkedIn example."""
    judge = judge or make_judge(mode=infer_plan(arms))
    cases = list(cases) if cases is not None else await load_cases()
    run = await run_eval(cases, arms, [judge], samples=samples, label=label, limiter=limiter)
    run_id = await save_run(run)
    return run_id, await load_run(run_id)


async def main() -> None:
    async with db.open_database(settings.database_url):
        run_id, df = await run_linkedin_eval([no_rag(), full_rag()], limiter=LlmCallLimiter(10, 50))
        print(f"run {run_id}: {len(df)} rows")


if __name__ == "__main__":
    asyncio.run(main())
