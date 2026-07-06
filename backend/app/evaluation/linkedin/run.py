"""Compose arms (+ optional judge) with the factory, run + persist one eval, return
(run_id, results). One arm -> pointwise, two -> pairwise; the judge matches that plan."""

from __future__ import annotations

import asyncio
from typing import Sequence

import pandas as pd

from ... import db
from ...config import settings
from ...llm import ONLINE, LlmExecutionStrategy
from ..framework import Arm, Case, Judge, load_run, run_eval, run_exists, save_run
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
    execution: LlmExecutionStrategy = ONLINE,
) -> tuple[str, pd.DataFrame]:
    """`judge` defaults to a judge matching the arm count; `cases` to every
    non-intro LinkedIn example. `execution` picks online vs batch dispatch."""
    judge = judge or make_judge(mode=infer_plan(arms))
    cases = list(cases) if cases is not None else await load_cases()
    run = await run_eval(cases, arms, [judge], samples=samples, label=label, execution=execution)
    run_id = await save_run(run)
    return run_id, await load_run(run_id)


async def run_or_load_linkedin_eval(
    run_id: str | None,
    arms: Sequence[Arm],
    judge: Judge | None = None,
    *,
    samples: int = 1,
    label: str | None = None,
    cases: Sequence[Case] | None = None,
    execution: LlmExecutionStrategy = ONLINE,
) -> tuple[str, pd.DataFrame]:
    if run_id is not None and await run_exists(run_id):
        return run_id, await load_run(run_id)
    return await run_linkedin_eval(arms, judge, samples=samples, label=label, cases=cases, execution=execution)


async def main() -> None:
    async with db.open_database(settings.database_url):
        run_id, df = await run_linkedin_eval(
            [no_rag(), full_rag()], execution=Execution(concurrency=10, max_calls_per_minute=50)
        )
        print(f"run {run_id}: {len(df)} rows")


if __name__ == "__main__":
    asyncio.run(main())
