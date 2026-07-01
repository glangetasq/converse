from __future__ import annotations

import asyncio
import unittest
from typing import Any, Sequence

from app.evaluation.framework.arm import Arm
from app.evaluation.framework.core import Candidate, Case, PairwiseJudgement, PointwiseJudgement
from app.evaluation.framework.runner import infer_plan, pair_ab, run_eval
from app.llm import Completion, GenConfig


class StubBuilder:
    """Returns a per-case prompt so a client can selectively fail on one case."""

    async def build(self, case: Case) -> str:
        return f"prompt::{case.id}"

    def spec(self) -> dict[str, Any]:
        return {"template": "stub"}


class StubClient:
    def __init__(self, *, fail_prompts: set[str] | None = None) -> None:
        self._fail = fail_prompts or set()

    async def generate(self, prompt: str, cfg: GenConfig, *, limiter: Any = None) -> Completion:
        if prompt in self._fail:
            raise RuntimeError("boom")
        return Completion(text=f"reply to {prompt}", usage={"total_tokens": 1})


class RecordingJudge:
    """Records the candidate ids each judge call received; returns a Judgement whose
    shape follows the candidate count."""

    mode = "recording"

    def __init__(self) -> None:
        self.seen: list[tuple[str, ...]] = []

    async def judge(
        self, case: Case, candidates: Sequence[Candidate], *, limiter: Any = None
    ) -> Any:
        self.seen.append(tuple(c.id for c in candidates))
        if len(candidates) == 1:
            return PointwiseJudgement(
                judge_name="j", scorecard_version="v1",
                subject_candidate_id=candidates[0].id, scores={},
            )
        return PairwiseJudgement(
            judge_name="j", scorecard_version="v1",
            candidate_a_id=candidates[0].id, candidate_b_id=candidates[1].id, winner="a",
        )

    def spec(self) -> dict[str, Any]:
        return {"name": "j", "mode": self.mode}


def _cfg() -> GenConfig:
    return GenConfig(model_name="gpt-5.4-nano")


def _arm(name: str, client: Any | None = None) -> Arm:
    return Arm(name=name, builder=StubBuilder(), client=client or StubClient(), cfg=_cfg())


def _cases(*ids: str) -> list[Case]:
    return [Case(id=i, thread=[], sender_name="A", recipient_name="B") for i in ids]


class InferPlanTests(unittest.TestCase):
    def test_one_arm_pointwise_two_arms_pairwise(self) -> None:
        self.assertEqual(infer_plan([_arm("a")]), "pointwise")
        self.assertEqual(infer_plan([_arm("a"), _arm("b")]), "pairwise")

    def test_zero_or_three_arms_rejected(self) -> None:
        with self.assertRaises(ValueError):
            infer_plan([])
        with self.assertRaises(ValueError):
            infer_plan([_arm("a"), _arm("b"), _arm("c")])


class PairAbTests(unittest.TestCase):
    def _c(self, arm: str, case: str, repeat: int) -> Candidate:
        return Candidate(case_id=case, arm_name=arm, repeat_index=repeat, text="x")

    def test_pairs_same_case_and_repeat_slot(self) -> None:
        cands = [self._c("a", "c1", 0), self._c("b", "c1", 0)]

        pairs = pair_ab(cands, "a", "b")

        self.assertEqual(len(pairs), 1)
        a, b = pairs[0]
        self.assertEqual((a.arm_name, b.arm_name), ("a", "b"))

    def test_drops_slots_missing_an_arm(self) -> None:
        cands = [
            self._c("a", "c1", 0), self._c("b", "c1", 0),   # complete slot
            self._c("a", "c2", 0),                           # b missing -> dropped
        ]

        pairs = pair_ab(cands, "a", "b")

        self.assertEqual([a.case_id for a, _ in pairs], ["c1"])


class RunEvalTests(unittest.TestCase):
    def test_pointwise_scores_each_error_free_candidate(self) -> None:
        judge = RecordingJudge()

        run = asyncio.run(run_eval(_cases("c1", "c2"), [_arm("no_rag")], [judge]))

        self.assertEqual(run.plan, "pointwise")
        self.assertEqual(len(run.candidates), 2)
        # one pointwise judgement per candidate, each seeing exactly one candidate
        self.assertEqual([len(s) for s in judge.seen], [1, 1])
        self.assertEqual(len(run.judgements), 2)

    def test_samples_produce_one_candidate_per_repeat(self) -> None:
        run = asyncio.run(run_eval(_cases("c1"), [_arm("no_rag")], [RecordingJudge()], samples=3))

        self.assertEqual(sorted(c.repeat_index for c in run.candidates), [0, 1, 2])

    def test_error_candidates_are_kept_but_not_judged(self) -> None:
        client = StubClient(fail_prompts={"prompt::c2"})
        judge = RecordingJudge()

        run = asyncio.run(run_eval(_cases("c1", "c2"), [_arm("no_rag", client)], [judge]))

        errored = {c.case_id: c.error for c in run.candidates}
        self.assertIsNone(errored["c1"])
        self.assertEqual(errored["c2"], "RuntimeError: boom")
        # only the error-free candidate was judged
        self.assertEqual(judge.seen, [("c1::no_rag::0",)])

    def test_pairwise_feeds_both_arms_to_the_judge(self) -> None:
        judge = RecordingJudge()

        run = asyncio.run(run_eval(_cases("c1"), [_arm("no_rag"), _arm("full_rag")], [judge]))

        self.assertEqual(run.plan, "pairwise")
        self.assertEqual(len(judge.seen), 1)
        self.assertEqual(len(judge.seen[0]), 2)   # judge got [a, b]

    def test_run_records_arm_and_judge_specs_and_git_meta(self) -> None:
        run = asyncio.run(run_eval(_cases("c1"), [_arm("no_rag")], [RecordingJudge()], label="exp"))

        self.assertEqual(run.label, "exp")
        self.assertEqual([s["name"] for s in run.arm_specs], ["no_rag"])
        self.assertEqual([s["name"] for s in run.judge_specs], ["j"])
        self.assertIn("git", run.meta)


if __name__ == "__main__":
    unittest.main()
