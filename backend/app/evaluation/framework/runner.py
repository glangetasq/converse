from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from ...llm.limiter import LlmCallLimiter
from ...utils import git_provenance
from .arm import Arm
from .core import Candidate, Case, Judgement
from .judges import Judge

Plan = Literal["pointwise", "pairwise"]


@dataclass
class EvalRun:
    """One run_eval result, pre-persistence (run_id is assigned in results.save_run)."""

    plan: Plan
    samples: int
    arm_specs: list[dict[str, Any]]
    judge_specs: list[dict[str, Any]]
    candidates: list[Candidate]
    judgements: list[Judgement]
    label: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def infer_plan(arms: Sequence[Arm]) -> Plan:
    if len(arms) == 1:
        return "pointwise"
    if len(arms) == 2:
        return "pairwise"
    raise ValueError("run_eval takes 1 arm (pointwise) or 2 arms (pairwise)")


async def run_eval(
    cases: Sequence[Case],
    arms: Sequence[Arm],
    judges: Sequence[Judge],
    *,
    samples: int = 1,
    label: str | None = None,
    limiter: LlmCallLimiter | None = None,
) -> EvalRun:
    plan = infer_plan(arms)

    candidates = list(
        await asyncio.gather(
            *(
                arm.run(case, repeat, limiter=limiter)
                for case in cases
                for arm in arms
                for repeat in range(samples)
            )
        )
    )

    case_by_id = {case.id: case for case in cases}
    scored = [c for c in candidates if c.error is None]

    if plan == "pointwise":
        judge_tasks = [
            judge.judge(case_by_id[c.case_id], [c], limiter=limiter)
            for c in scored
            for judge in judges
        ]
    else:
        judge_tasks = [
            judge.judge(case_by_id[a.case_id], [a, b], limiter=limiter)
            for a, b in pair_ab(scored, arms[0].name, arms[1].name)
            for judge in judges
        ]
    judgements = list(await asyncio.gather(*judge_tasks))

    return EvalRun(
        plan=plan,
        samples=samples,
        arm_specs=[arm.spec() for arm in arms],
        judge_specs=[judge.spec() for judge in judges],
        candidates=candidates,
        judgements=judgements,
        label=label,
        meta={"git": git_provenance()},
    )


def pair_ab(
    candidates: Sequence[Candidate],
    arm_a: str,
    arm_b: str,
) -> list[tuple[Candidate, Candidate]]:
    """Pair each arm_a candidate with the arm_b one from the same (case, sample), so a
    comparison is always same-case same-sample. Slots missing either arm are dropped."""
    slot = lambda c: (c.case_id, c.repeat_index)   # noqa: E731
    a_by_slot = {slot(c): c for c in candidates if c.arm_name == arm_a}
    b_by_slot = {slot(c): c for c in candidates if c.arm_name == arm_b}
    return [
        (a_by_slot[s], b_by_slot[s])
        for s in sorted(a_by_slot.keys() & b_by_slot.keys())
    ]
