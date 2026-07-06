"""One judge call scores the whole scorecard via generate_structured. PairwiseJudge
runs both candidate orders to cancel position bias."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from ...llm import ONLINE, GenConfig, LlmExecutionStrategy, ProviderClient
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

    def spec(self) -> dict[str, Any]:
        """Snapshot of the prompt; template builders override to pin their fingerprint."""
        return {"builder": type(self).__name__}


class Judge(ABC):
    mode: str
    logic_version: str = "v1"  # bump when the judging methodology changes

    def __init__(
        self,
        name: str,
        scorecard: Scorecard,
        client: ProviderClient,
        model: str,
        cfg: GenConfig,
        prompt: JudgePromptBuilder,
    ) -> None:
        self.name = name
        self.scorecard = scorecard
        self.client = client
        self.model = model
        self.cfg = cfg
        self.prompt = prompt

    def build_prompt(self, case: Case, candidates: Sequence[Candidate]) -> str:
        return self.prompt.build(case, candidates, self.scorecard)

    def spec(self) -> dict[str, Any]:
        """Snapshot of what scored a run — counterpart to Arm.spec()."""
        return {
            "name": self.name,
            "mode": self.mode,
            "model": self.model,
            "logic_version": self.logic_version,
            "gen": self.cfg.spec(),
            "prompt": self.prompt.spec(),
            "scorecard": self.scorecard.spec(),
        }

    @abstractmethod
    def prompts(self, case: Case, candidates: Sequence[Candidate]) -> list[str]:
        """The judge call(s) for this candidate set — one for pointwise, two (both
        candidate orders) for pairwise. Raises on the wrong candidate count."""
        raise NotImplementedError

    @abstractmethod
    def schema(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def assemble(
        self,
        case: Case,
        candidates: Sequence[Candidate],
        outcomes: Sequence[dict[str, Any] | BaseException],
    ) -> PointwiseJudgement | PairwiseJudgement:
        """Fold the structured result(s) into a judgement; a BaseException outcome
        becomes the judgement's `.error`. Shared by the online and batch paths."""
        raise NotImplementedError

    async def judge(
        self,
        case: Case,
        candidates: Sequence[Candidate],
        *,
        execution: LlmExecutionStrategy = ONLINE,
    ) -> PointwiseJudgement | PairwiseJudgement:
        schema = self.schema()
        outcomes: list[dict[str, Any] | BaseException] = []
        for prompt in self.prompts(case, candidates):
            try:
                outcomes.append(
                    await self.client.generate_structured(prompt, schema, self.model, self.cfg, execution=execution)
                )
            except Exception as error:  # noqa: BLE001 — errors are data here
                outcomes.append(error)
        return self.assemble(case, candidates, outcomes)


class PointwiseJudge(Judge):
    mode = "pointwise"
    logic_version = "pointwise-v1"

    def prompts(self, case: Case, candidates: Sequence[Candidate]) -> list[str]:
        if len(candidates) != 1:
            raise ValueError("pointwise judging scores exactly one candidate")
        return [self.build_prompt(case, candidates)]

    def schema(self) -> dict[str, Any]:
        return self.scorecard.pointwise_schema()

    def assemble(
        self,
        case: Case,
        candidates: Sequence[Candidate],
        outcomes: Sequence[dict[str, Any] | BaseException],
    ) -> PointwiseJudgement:
        base = PointwiseJudgement(
            judge_name=self.name,
            scorecard_version=self.scorecard.version,
            subject_candidate_id=candidates[0].id,
        )
        result = outcomes[0]
        if isinstance(result, BaseException):
            base.error = f"{type(result).__name__}: {result}"
            return base
        base.scores = {m.key: result[m.key] for m in self.scorecard.metrics}
        base.rationale = result.get(RATIONALE_KEY)
        return base


class PairwiseJudge(Judge):
    mode = "pairwise"
    logic_version = "pairwise-v1"

    def prompts(self, case: Case, candidates: Sequence[Candidate]) -> list[str]:
        if len(candidates) != 2:
            raise ValueError("pairwise judging compares exactly two candidates")
        a, b = candidates
        return [self.build_prompt(case, [a, b]), self.build_prompt(case, [b, a])]

    def schema(self) -> dict[str, Any]:
        return self.scorecard.pairwise_schema()

    def assemble(
        self,
        case: Case,
        candidates: Sequence[Candidate],
        outcomes: Sequence[dict[str, Any] | BaseException],
    ) -> PairwiseJudgement:
        a, b = candidates
        base = PairwiseJudgement(
            judge_name=self.name,
            scorecard_version=self.scorecard.version,
            candidate_a_id=a.id,
            candidate_b_id=b.id,
        )
        error = next((o for o in outcomes if isinstance(o, BaseException)), None)
        if error is not None:
            base.error = f"{type(error).__name__}: {error}"
            return base
        forward, reversed_ = outcomes
        base.preference = {
            m.key: self._reconcile(forward.get(m.key), reversed_.get(m.key)) for m in self.scorecard.metrics
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
