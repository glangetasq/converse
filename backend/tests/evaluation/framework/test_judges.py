from __future__ import annotations

import asyncio
import unittest
from typing import Any, Sequence

from app.evaluation.framework.core import Candidate, Case
from app.evaluation.framework.judges import (
    JudgePromptBuilder,
    PairwiseJudge,
    PointwiseJudge,
)
from app.evaluation.framework.scorecard import Metric, Scorecard
from app.llm import GenConfig

SCORECARD = Scorecard(
    version="v1",
    metrics=(Metric("relevance", "on-topic"), Metric("tone", "voice match")),
)


class StubJudgePromptBuilder(JudgePromptBuilder):
    """Renders a deterministic prompt from the candidate order so tests can assert
    which order each pass was shown."""

    def build(self, case: Case, candidates: Sequence[Candidate], scorecard: Scorecard) -> str:
        return "compare " + " vs ".join(c.arm_name for c in candidates)


class StubStructuredClient:
    """Duck-types ProviderClient.generate_structured: pops canned dicts in order
    and records (prompt, schema) per call."""

    def __init__(self, responses: list[dict], *, raises: Exception | None = None) -> None:
        self._responses = list(responses)
        self._raises = raises
        self.calls: list[tuple[str, dict]] = []

    async def generate_structured(
        self, prompt: str, schema: dict, model: str, cfg: GenConfig, *, execution: Any = None
    ) -> dict:
        self.calls.append((prompt, schema))
        if self._raises is not None:
            raise self._raises
        return self._responses.pop(0)


def _case() -> Case:
    return Case(id="c1", thread=[], sender_name="A", recipient_name="B")


def _cand(arm: str) -> Candidate:
    return Candidate(case_id="c1", arm_name=arm, repeat_index=0, text=f"msg from {arm}")


def _pointwise(client: Any) -> PointwiseJudge:
    return PointwiseJudge("j", SCORECARD, client, "m", GenConfig(), StubJudgePromptBuilder())


def _pairwise(client: Any) -> PairwiseJudge:
    return PairwiseJudge("j", SCORECARD, client, "m", GenConfig(), StubJudgePromptBuilder())


class JudgeSpecTests(unittest.TestCase):
    def test_spec_snapshots_model_prompt_scorecard_and_logic(self) -> None:
        spec = _pairwise(StubStructuredClient([])).spec()
        self.assertEqual(spec["name"], "j")
        self.assertEqual(spec["mode"], "pairwise")
        self.assertEqual(spec["logic_version"], "pairwise-v1")
        self.assertEqual(spec["model"], "m")
        self.assertEqual(spec["scorecard"]["fingerprint"], SCORECARD.fingerprint)

    def test_pointwise_and_pairwise_logic_versions_differ(self) -> None:
        self.assertNotEqual(
            _pointwise(StubStructuredClient([])).spec()["logic_version"],
            _pairwise(StubStructuredClient([])).spec()["logic_version"],
        )


class PointwiseJudgeTests(unittest.TestCase):
    def test_one_call_scores_all_metrics(self) -> None:
        client = StubStructuredClient([{"relevance": 4, "tone": 5, "rationale": "solid"}])
        judge = _pointwise(client)

        j = asyncio.run(judge.judge(_case(), [_cand("no_rag")]))

        self.assertEqual(len(client.calls), 1)  # single call, all metrics
        self.assertEqual(j.scores, {"relevance": 4, "tone": 5})
        self.assertEqual(j.rationale, "solid")
        self.assertEqual(j.subject_candidate_id, "c1::no_rag::0")
        self.assertEqual(j.scorecard_version, "v1")
        self.assertIsNone(j.error)
        # The scorecard-derived schema was passed to the client.
        self.assertEqual(client.calls[0][1], SCORECARD.pointwise_schema())

    def test_wrong_candidate_count_raises(self) -> None:
        judge = _pointwise(StubStructuredClient([]))
        with self.assertRaises(ValueError):
            asyncio.run(judge.judge(_case(), [_cand("a"), _cand("b")]))

    def test_error_captured_into_judgement(self) -> None:
        judge = _pointwise(StubStructuredClient([], raises=RuntimeError("429")))

        j = asyncio.run(judge.judge(_case(), [_cand("no_rag")]))

        self.assertEqual(j.error, "RuntimeError: 429")
        self.assertIsNone(j.scores)
        self.assertEqual(j.subject_candidate_id, "c1::no_rag::0")


class PairwiseJudgeTests(unittest.TestCase):
    def _run(self, forward: dict, reversed_: dict):
        client = StubStructuredClient([forward, reversed_])
        result = asyncio.run(_pairwise(client).judge(_case(), [_cand("no_rag"), _cand("full_rag")]))
        return result, client

    def test_runs_both_orders(self) -> None:
        _, client = self._run(
            {"relevance": "a", "tone": "a", "rationale": "x"},
            {"relevance": "b", "tone": "b", "rationale": "y"},
        )
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(client.calls[0][0], "compare no_rag vs full_rag")
        self.assertEqual(client.calls[1][0], "compare full_rag vs no_rag")

    def test_consistent_winner_survives_order_swap(self) -> None:
        # Candidate A wins whichever position it's shown in: 'a' forward, 'b' reversed.
        result, _ = self._run(
            {"relevance": "a", "tone": "a", "rationale": "A better"},
            {"relevance": "b", "tone": "b", "rationale": "A better"},
        )
        self.assertEqual(result.preference, {"relevance": "a", "tone": "a"})
        self.assertEqual(result.winner, "a")
        self.assertEqual(result.candidate_a_id, "c1::no_rag::0")
        self.assertEqual(result.candidate_b_id, "c1::full_rag::0")

    def test_position_bias_collapses_to_tie(self) -> None:
        # A judge that always prefers the first-shown candidate ('a' both passes)
        # must not produce a winner.
        result, _ = self._run(
            {"relevance": "a", "tone": "a", "rationale": "first"},
            {"relevance": "a", "tone": "a", "rationale": "first"},
        )
        self.assertEqual(result.preference, {"relevance": "tie", "tone": "tie"})
        self.assertEqual(result.winner, "tie")

    def test_explicit_ties_and_split_winner(self) -> None:
        result, _ = self._run(
            {"relevance": "tie", "tone": "a", "rationale": ""},
            {"relevance": "tie", "tone": "b", "rationale": ""},
        )
        # relevance: tie both -> tie. tone: a forward, b reversed -> A -> 'a'.
        self.assertEqual(result.preference, {"relevance": "tie", "tone": "a"})
        self.assertEqual(result.winner, "a")

    def test_rationales_merged_from_both_orders(self) -> None:
        result, _ = self._run(
            {"relevance": "a", "tone": "a", "rationale": "fwd"},
            {"relevance": "b", "tone": "b", "rationale": "rev"},
        )
        self.assertEqual(result.rationale, "[a,b] fwd\n[b,a] rev")

    def test_error_captured_into_judgement(self) -> None:
        judge = _pairwise(StubStructuredClient([], raises=RuntimeError("500")))

        j = asyncio.run(judge.judge(_case(), [_cand("no_rag"), _cand("full_rag")]))

        self.assertEqual(j.error, "RuntimeError: 500")
        self.assertIsNone(j.preference)
        self.assertIsNone(j.winner)


if __name__ == "__main__":
    unittest.main()
