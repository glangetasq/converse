from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Sequence

from ...llm import ONLINE, BatchRequest, Completion, LlmExecutionStrategy, ModelError, ProviderClient
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
    execution: LlmExecutionStrategy = ONLINE,
) -> EvalRun:
    """Generate candidates, then judge them. `execution` picks the dispatch strategy:
    online (concurrent, under a limiter) or batch (provider Batch API). Both paths
    produce identical EvalRun shapes."""
    plan = infer_plan(arms)

    if execution.batch:
        candidates = await _batch_candidates(cases, arms, samples)
    else:
        candidates = list(
            await asyncio.gather(
                *(
                    arm.run(case, repeat, execution=execution)
                    for case in cases
                    for arm in arms
                    for repeat in range(samples)
                )
            )
        )

    case_by_id = {case.id: case for case in cases}
    scored = [c for c in candidates if c.error is None]
    units = _judge_units(plan, scored, arms, judges, case_by_id)

    if execution.batch:
        judgements = await _batch_judgements(units)
    else:
        judgements = list(
            await asyncio.gather(*(judge.judge(case, cands, execution=execution) for judge, case, cands in units))
        )

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


JudgeUnit = tuple[Judge, Case, list[Candidate]]


def _judge_units(
    plan: Plan,
    scored: list[Candidate],
    arms: Sequence[Arm],
    judges: Sequence[Judge],
    case_by_id: dict[str, Case],
) -> list[JudgeUnit]:
    if plan == "pointwise":
        return [(judge, case_by_id[c.case_id], [c]) for c in scored for judge in judges]
    return [
        (judge, case_by_id[a.case_id], [a, b])
        for a, b in pair_ab(scored, arms[0].name, arms[1].name)
        for judge in judges
    ]


async def _dispatch(items: list[tuple[ProviderClient, BatchRequest]]) -> dict[str, Completion | ModelError]:
    """Group requests by provider client, submit one batch each, and merge the results
    (custom_ids are globally unique). A whole-batch failure degrades to per-item errors."""
    by_client: dict[ProviderClient, list[BatchRequest]] = defaultdict(list)
    for client, req in items:
        by_client[client].append(req)

    async def run_one(client: ProviderClient, reqs: list[BatchRequest]) -> dict[str, Completion | ModelError]:
        try:
            return await client.run_batch(reqs)
        except Exception as error:  # noqa: BLE001 — whole-batch failure is data, not fatal
            return {r.custom_id: ModelError(f"{client.suite} batch failed: {error}") for r in reqs}

    merged: dict[str, Completion | ModelError] = {}
    for result in await asyncio.gather(*(run_one(client, reqs) for client, reqs in by_client.items())):
        merged.update(result)
    return merged


async def _batch_candidates(cases: Sequence[Case], arms: Sequence[Arm], samples: int) -> list[Candidate]:
    specs = [(case, arm, repeat) for case in cases for arm in arms for repeat in range(samples)]
    builts = await asyncio.gather(*(arm.builder.build(case) for case, arm, _ in specs), return_exceptions=True)

    items: list[tuple[ProviderClient, BatchRequest]] = []
    contexts = []
    for index, ((case, arm, repeat), built) in enumerate(zip(specs, builts)):
        custom_id = str(index)
        contexts.append((case, arm, repeat, built, custom_id))
        if not isinstance(built, BaseException):
            items.append((arm.client, BatchRequest(custom_id, built.prompt, arm.model, arm.cfg)))

    results = await _dispatch(items)
    candidates = []
    for case, arm, repeat, built, custom_id in contexts:
        if isinstance(built, BaseException):
            candidates.append(arm.failed(case, repeat, built))
            continue
        outcome = results.get(custom_id, ModelError("batch returned no result"))
        if isinstance(outcome, Completion):
            candidates.append(arm.candidate(case, repeat, built, outcome))
        else:
            candidates.append(arm.failed(case, repeat, outcome, prompt=built.prompt))
    return candidates


async def _batch_judgements(units: list[JudgeUnit]) -> list[Judgement]:
    items: list[tuple[ProviderClient, BatchRequest]] = []
    plans = []
    counter = 0
    for judge, case, candidates in units:
        cfg = replace(judge.cfg, schema=judge.schema())
        custom_ids = []
        for prompt in judge.prompts(case, candidates):
            custom_id = str(counter)
            counter += 1
            custom_ids.append(custom_id)
            items.append((judge.client, BatchRequest(custom_id, prompt, judge.model, cfg)))
        plans.append((judge, case, candidates, custom_ids))

    results = await _dispatch(items)
    judgements = []
    for judge, case, candidates, custom_ids in plans:
        outcomes = [_structured_outcome(judge.client, results.get(cid)) for cid in custom_ids]
        judgements.append(judge.assemble(case, candidates, outcomes))
    return judgements


def _structured_outcome(
    client: ProviderClient, outcome: Completion | ModelError | None
) -> dict[str, Any] | BaseException:
    """Turn a batched completion into the parsed-JSON dict a judge's `assemble` expects,
    mirroring generate_structured's own parse; errors pass through as-is."""
    if outcome is None:
        return ModelError(f"{client.suite} batch returned no result")
    if isinstance(outcome, BaseException):
        return outcome
    try:
        return json.loads(outcome.text)
    except json.JSONDecodeError:
        return ModelError(f"{client.suite} structured output was not valid JSON", response_body=outcome.text)


def pair_ab(
    candidates: Sequence[Candidate],
    arm_a: str,
    arm_b: str,
) -> list[tuple[Candidate, Candidate]]:
    """Pair each arm_a candidate with the arm_b one from the same (case, sample), so a
    comparison is always same-case same-sample. Slots missing either arm are dropped."""
    slot = lambda c: (c.case_id, c.repeat_index)  # noqa: E731
    a_by_slot = {slot(c): c for c in candidates if c.arm_name == arm_a}
    b_by_slot = {slot(c): c for c in candidates if c.arm_name == arm_b}
    return [(a_by_slot[s], b_by_slot[s]) for s in sorted(a_by_slot.keys() & b_by_slot.keys())]
