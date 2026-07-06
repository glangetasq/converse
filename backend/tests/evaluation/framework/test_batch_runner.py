from __future__ import annotations

import asyncio
import json
import unittest
from typing import Any, Sequence

from app.evaluation.framework import run_eval
from app.evaluation.framework.arm import Arm
from app.evaluation.framework.core import Candidate, Case, PointwiseJudgement
from app.llm import BatchRequest, Completion, GenConfig, LlmExecutionStrategy


class StubBuilder:
    def __init__(self, fail: set[str] | None = None) -> None:
        self._fail = fail or set()

    async def build(self, case: Case):
        if case.id in self._fail:
            raise ValueError("no facts")
        from app.prompting import BuiltPrompt

        return BuiltPrompt(f"prompt::{case.id}")

    def spec(self) -> dict[str, Any]:
        return {"template": "stub"}


class StubBatchClient:
    """run_batch echoes each request: structured calls (schema set) return JSON, plain
    calls return text. `missing` custom_ids are dropped to exercise the error path."""

    suite = "stub"

    def __init__(self, *, missing: set[str] | None = None) -> None:
        self._missing = missing or set()

    async def run_batch(self, requests: list[BatchRequest]) -> dict[str, Completion]:
        out = {}
        for req in requests:
            if req.custom_id in self._missing:
                continue
            if req.cfg.schema is not None:
                out[req.custom_id] = Completion(text=json.dumps({"prompt": req.prompt}))
            else:
                out[req.custom_id] = Completion(text=f"gen::{req.prompt}", usage={"total_tokens": 1})
        return out


class StubJudge:
    mode = "pointwise"
    logic_version = "stub-v1"

    def __init__(self, client: StubBatchClient) -> None:
        self.client = client
        self.model = "judge-model"
        self.cfg = GenConfig()

    def prompts(self, case: Case, candidates: Sequence[Candidate]) -> list[str]:
        return [f"judge::{candidates[0].text}"]

    def schema(self) -> dict[str, Any]:
        return {"type": "object"}

    def assemble(self, case, candidates, outcomes) -> PointwiseJudgement:
        base = PointwiseJudgement(judge_name="stub", scorecard_version="v1", subject_candidate_id=candidates[0].id)
        outcome = outcomes[0]
        if isinstance(outcome, BaseException):
            base.error = str(outcome)
        else:
            base.scores = {"n": 1}
            base.rationale = outcome["prompt"]
        return base

    def spec(self) -> dict[str, Any]:
        return {"name": "stub", "mode": self.mode}


def _case(cid: str) -> Case:
    return Case(id=cid, thread=[], sender_name="A", recipient_name="B")


def _arm(client: StubBatchClient) -> Arm:
    return Arm(name="no_rag", builder=StubBuilder(), client=client, model="arm-model", cfg=GenConfig())


class BatchRunTests(unittest.TestCase):
    def test_batched_candidates_and_judgements(self) -> None:
        client = StubBatchClient()
        run = asyncio.run(
            run_eval(
                [_case("c1"), _case("c2")],
                [_arm(client)],
                [StubJudge(client)],
                execution=LlmExecutionStrategy(batch=True),
            )
        )
        self.assertEqual({c.case_id for c in run.candidates}, {"c1", "c2"})
        self.assertEqual(sorted(c.text for c in run.candidates), ["gen::prompt::c1", "gen::prompt::c2"])
        self.assertTrue(all(c.error is None for c in run.candidates))
        # each judgement's rationale is the judge prompt, proving the structured
        # completion round-tripped through JSON parsing and assemble()
        self.assertEqual(
            sorted(j.rationale for j in run.judgements),
            ["judge::gen::prompt::c1", "judge::gen::prompt::c2"],
        )

    def test_build_failure_skips_generation_and_judging(self) -> None:
        client = StubBatchClient()
        arm = Arm(name="no_rag", builder=StubBuilder(fail={"c2"}), client=client, model="m", cfg=GenConfig())
        run = asyncio.run(
            run_eval([_case("c1"), _case("c2")], [arm], [StubJudge(client)], execution=LlmExecutionStrategy(batch=True))
        )

        failed = [c for c in run.candidates if c.error is not None]
        self.assertEqual([c.case_id for c in failed], ["c2"])
        self.assertIn("ValueError", failed[0].error)
        self.assertEqual(len(run.judgements), 1)  # only the c1 candidate was scored

    def test_missing_batch_result_becomes_error_candidate(self) -> None:
        # custom_id "0" is the first (only) candidate request
        client = StubBatchClient(missing={"0"})
        run = asyncio.run(
            run_eval([_case("c1")], [_arm(client)], [StubJudge(client)], execution=LlmExecutionStrategy(batch=True))
        )

        self.assertEqual(len(run.candidates), 1)
        self.assertIsNotNone(run.candidates[0].error)
        self.assertEqual(run.judgements, [])


if __name__ == "__main__":
    unittest.main()
