from __future__ import annotations

import dataclasses
import unittest

from app.evaluation.framework.core import (
    Candidate,
    Case,
    PairwiseJudgement,
    PointwiseJudgement,
)


class CaseTests(unittest.TestCase):
    def test_case_is_frozen_with_defaults(self) -> None:
        case = Case(
            id="c1",
            thread=[{"body": "hi", "sender_name": "A"}],
            sender_name="A",
            recipient_name="B",
        )
        self.assertIsNone(case.ground_truth)
        self.assertEqual(case.meta, {})
        with self.assertRaises(dataclasses.FrozenInstanceError):
            case.sender_name = "X"  # type: ignore[misc]

    def test_meta_defaults_are_independent(self) -> None:
        a = Case(id="a", thread=[], sender_name="A", recipient_name="B")
        b = Case(id="b", thread=[], sender_name="A", recipient_name="B")
        self.assertIsNot(a.meta, b.meta)


class CandidateTests(unittest.TestCase):
    def test_error_defaults_none_and_usage_isolated(self) -> None:
        c1 = Candidate(case_id="c", arm_name="v", repeat_index=0, text="hello")
        c2 = Candidate(case_id="c", arm_name="v", repeat_index=1, text="bye")
        self.assertIsNone(c1.error)
        self.assertEqual(c1.usage, {})
        c1.usage["tokens"] = 5
        self.assertEqual(c2.usage, {})


class JudgementTests(unittest.TestCase):
    def test_pointwise_shape(self) -> None:
        j = PointwiseJudgement(
            judge_name="j",
            scorecard_version="v1",
            subject_candidate_id="cand-1",
            scores={"relevance": 4},
        )
        self.assertEqual(j.scores, {"relevance": 4})
        # No pairwise fields leak onto a pointwise judgement.
        self.assertFalse(hasattr(j, "preference"))

    def test_pairwise_shape(self) -> None:
        j = PairwiseJudgement(
            judge_name="j",
            scorecard_version="v1",
            candidate_a_id="a",
            candidate_b_id="b",
            preference={"relevance": "a"},
            winner="a",
        )
        self.assertEqual(j.preference, {"relevance": "a"})
        self.assertEqual(j.winner, "a")
        self.assertFalse(hasattr(j, "scores"))


if __name__ == "__main__":
    unittest.main()
