"""One judge call scores the whole scorecard via generate_structured. PairwiseJudge
runs both candidate orders to cancel position bias."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from ...llm import GenConfig, LlmCallLimiter, ProviderClient
from .core import Candidate, Case, PairwiseJudgement, PointwiseJudgement
from .scorecard import RATIONALE_KEY, Scorecard

# un-flips a pass-2 vote (b shown first) back onto the real candidates
_FLIP = {"a": "b", "b": "a", "tie": "tie"}


class JudgePromptBuilder(ABC):
    """Renders one judge prompt; needs the candidate(s) and scorecard, not just the
    Case. Domain-agnostic — each eval supplies the concrete builder."""

    @abstractmethod
    def build(
        self,
        case: Case,
        candidates: Sequence[Candidate],
        scorecard: Scorecard,
    ) -> str:
        raise NotImplementedError


class Judge(ABC):
    mode: str

    def __init__(
        self,
        name: str,
        scorecard: Scorecard,
        client: ProviderClient,
        cfg: GenConfig,
        prompt: JudgePromptBuilder,
    ) -> None:
        self.name = name
        self.scorecard = scorecard
        self.client = client
        self.cfg = cfg
        self.prompt = prompt

    def build_prompt(self, case: Case, candidates: Sequence[Candidate]) -> str:
        return self.prompt.build(case, candidates, self.scorecard)

    @abstractmethod
    async def judge(
        self,
        case: Case,
        candidates: Sequence[Candidate],
        *,
        limiter: LlmCallLimiter | None = None,
    ) -> PointwiseJudgement | PairwiseJudgement:
        raise NotImplementedError


class PointwiseJudge(Judge):
    mode = "pointwise"

    async def judge(
        self,
        case: Case,
        candidates: Sequence[Candidate],
        *,
        limiter: LlmCallLimiter | None = None,
    ) -> PointwiseJudgement:
        if len(candidates) != 1:
            raise ValueError("pointwise judging scores exactly one candidate")
        candidate = candidates[0]
        base = PointwiseJudgement(
            judge_name=self.name,
            scorecard_version=self.scorecard.version,
            subject_candidate_id=candidate.id,
        )
        try:
            result = await self.client.generate_structured(
                self.build_prompt(case, candidates),
                self.scorecard.pointwise_schema(),
                self.cfg,
                limiter=limiter,
            )
        except Exception as error:  # noqa: BLE001 — errors are data here
            base.error = f"{type(error).__name__}: {error}"
            return base
        base.scores = {m.key: result[m.key] for m in self.scorecard.metrics}
        base.rationale = result.get(RATIONALE_KEY)
        return base


class PairwiseJudge(Judge):
    mode = "pairwise"

    async def judge(
        self,
        case: Case,
        candidates: Sequence[Candidate],
        *,
        limiter: LlmCallLimiter | None = None,
    ) -> PairwiseJudgement:
        if len(candidates) != 2:
            raise ValueError("pairwise judging compares exactly two candidates")
        a, b = candidates
        base = PairwiseJudgement(
            judge_name=self.name,
            scorecard_version=self.scorecard.version,
            candidate_a_id=a.id,
            candidate_b_id=b.id,
        )
        schema = self.scorecard.pairwise_schema()
        try:
            # pass 1 shows (a, b); pass 2 shows (b, a)
            forward = await self.client.generate_structured(
                self.build_prompt(case, [a, b]), schema, self.cfg, limiter=limiter
            )
            reversed_ = await self.client.generate_structured(
                self.build_prompt(case, [b, a]), schema, self.cfg, limiter=limiter
            )
        except Exception as error:  # noqa: BLE001 — errors are data here
            base.error = f"{type(error).__name__}: {error}"
            return base
        base.preference = {
            m.key: self._reconcile(forward.get(m.key), reversed_.get(m.key))
            for m in self.scorecard.metrics
        }
        base.winner = self._winner(base.preference)
        base.rationale = self._merge_rationales(forward, reversed_)
        return base

    @staticmethod
    def _reconcile(forward_vote: str | None, reversed_vote: str | None) -> str:
        """Fold both orders into one preference; the flipped pass is un-flipped
        first, and any disagreement (position bias) becomes a tie."""
        real_forward = forward_vote if forward_vote in _FLIP else "tie"
        real_reversed = _FLIP.get(reversed_vote or "tie", "tie")
        return real_forward if real_forward == real_reversed else "tie"

    @staticmethod
    def _winner(preference: dict[str, str]) -> str:
        a_wins = sum(1 for v in preference.values() if v == "a")
        b_wins = sum(1 for v in preference.values() if v == "b")
        if a_wins > b_wins:
            return "a"
        if b_wins > a_wins:
            return "b"
        return "tie"

    @staticmethod
    def _merge_rationales(forward: dict, reversed_: dict) -> str | None:
        parts = []
        if forward.get(RATIONALE_KEY):
            parts.append(f"[a,b] {forward[RATIONALE_KEY]}")
        if reversed_.get(RATIONALE_KEY):
            parts.append(f"[b,a] {reversed_[RATIONALE_KEY]}")
        return "\n".join(parts) or None
