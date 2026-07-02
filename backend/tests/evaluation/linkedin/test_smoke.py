from __future__ import annotations

import asyncio
import unittest
from datetime import datetime
from unittest.mock import patch

from app.evaluation.framework import PairwiseJudge, PointwiseJudge, run_eval
from app.evaluation.framework.core import Candidate, Case
from app.evaluation.linkedin import factory, full_rag, judge, no_rag, scorecard
from app.llm import Completion, GenConfig
from app.retrieval import RetrievalConfig
from app.retrieval.search import FactRow, RetrievedFact

_KEYS = scorecard().metric_keys
_POINT = {**{k: 4 for k in _KEYS}, "rationale": "ok"}
_PAIR = {**{k: "b" for k in _KEYS}, "rationale": "ok"}


class StubClient:
    """One stub for both roles: suggestion text + canned structured judge output."""

    def __init__(self, structured: dict) -> None:
        self._structured = structured

    async def generate(self, prompt, cfg, *, limiter=None):
        return Completion(text="stub suggestion", usage={})

    async def generate_structured(self, prompt, schema, cfg, *, limiter=None):
        return dict(self._structured)


def _case(cid: str = "c1") -> Case:
    thread = [{"sender_name": "Alice", "body": "hi"}]
    return Case(
        id=cid,
        thread=thread,
        sender_name="Alice",
        recipient_name="Bob",
        ground_truth="sure",
        meta={"user_id": "u1", "person_id": "p1", "thread_depth": len(thread)},
    )


class FactoryTests(unittest.TestCase):
    def test_arm_variants_flip_only_their_knob(self) -> None:
        self.assertIsNone(no_rag().builder.spec()["augment"])
        self.assertEqual(full_rag(rag=RetrievalConfig(k=12)).builder.spec()["augment"], {"name": "rag", "k": 12})
        variant = no_rag(gen=GenConfig(model_name="gpt-5.4-nano", temperature=0.5))
        self.assertEqual(variant.cfg.temperature, 0.5)

    def test_judge_modes_pick_kind_and_prompt(self) -> None:
        self.assertIsInstance(judge(), PointwiseJudge)
        self.assertIsInstance(judge(mode="pairwise"), PairwiseJudge)
        self.assertEqual(judge().prompt.spec()["mode"], "pointwise")
        self.assertEqual(judge(mode="pairwise").prompt.spec()["mode"], "pairwise")

    def test_judge_prompts_render_the_candidates(self) -> None:
        case = _case()
        a = Candidate(case_id="c1", arm_name="no_rag", repeat_index=0, text="A msg")
        b = Candidate(case_id="c1", arm_name="full_rag", repeat_index=0, text="B msg")
        pw = judge().prompt.build(case, [a], scorecard())
        pr = judge(mode="pairwise").prompt.build(case, [a, b], scorecard())
        self.assertIn("A msg", pw)
        for needle in ("Suggestion A", "Suggestion B", "A msg", "B msg"):
            self.assertIn(needle, pr)


class RunSmokeTests(unittest.TestCase):
    def test_pointwise_end_to_end(self) -> None:
        with patch.object(factory, "get_client", lambda _n: StubClient(_POINT)):
            arm, j = no_rag(), judge()
        run = asyncio.run(run_eval([_case("c1"), _case("c2")], [arm], [j]))
        self.assertEqual(run.plan, "pointwise")
        self.assertEqual(len(run.judgements), 2)
        self.assertEqual(run.judgements[0].scores["clarity"], 4)

    def test_full_rag_injects_retrieved_facts(self) -> None:
        fact = RetrievedFact(
            fact=FactRow(
                id="1",
                person_id="p1",
                memory_type="about",
                content="Bob leads infra",
                created_at=datetime(2026, 1, 1),
                embedding=[0.0],
            ),
            label="about_them",
        )

        async def fake_retrieve(user_id, person_id, thread, *, config):
            return [fact]

        with patch.object(factory, "get_client", lambda _n: StubClient(_POINT)):
            arm = full_rag()
        with patch("app.prompting.rag.retrieve_facts_for_thread", new=fake_retrieve):
            run = asyncio.run(run_eval([_case()], [arm], []))
        self.assertIn("Bob leads infra", run.candidates[0].prompt)

    def test_pairwise_end_to_end(self) -> None:
        async def fake_retrieve(user_id, person_id, thread, *, config):
            return []

        with patch.object(factory, "get_client", lambda _n: StubClient(_PAIR)):
            arms, j = [no_rag(), full_rag()], judge(mode="pairwise")
        with patch("app.prompting.rag.retrieve_facts_for_thread", new=fake_retrieve):
            run = asyncio.run(run_eval([_case()], arms, [j]))
        self.assertEqual(run.plan, "pairwise")
        self.assertEqual(len(run.judgements), 1)
        result = run.judgements[0]
        self.assertEqual(set(result.preference), set(_KEYS))  # every metric compared
        self.assertIn(result.winner, ("a", "b", "tie"))


if __name__ == "__main__":
    unittest.main()
