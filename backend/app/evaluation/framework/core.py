from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from ...prompting import Thread  # Case structurally satisfies PromptContext

JudgeMode = Literal["pointwise", "pairwise"]


@dataclass(frozen=True)
class Case:
    id: str
    thread: Thread
    sender_name: str
    recipient_name: str
    ground_truth: str | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class Candidate:
    case_id: str
    arm_name: str
    repeat_index: int  # 0-based repeat for one (case, arm)
    text: str
    prompt: str | None = None
    evidence: str | None = None  # facts the arm retrieved, for the judge to score groundedness against
    provenance: dict[str, Any] = field(default_factory=dict)  # machine-readable trace from the builder
    usage: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def id(self) -> str:
        """Stable id a Judgement points back to."""
        return f"{self.case_id}::{self.arm_name}::{self.repeat_index}"


@dataclass
class Judgement:
    """Common verdict fields; mode-specific ones live on the subclasses."""

    judge_name: str
    scorecard_version: str
    rationale: str | None = None
    error: str | None = None


@dataclass
class PointwiseJudgement(Judgement):
    """One candidate scored on every scorecard metric in one call."""

    subject_candidate_id: str | None = None
    scores: dict[str, int] | None = None  # {metric: score-in-scale}
    verdict: str | None = None  # optional summary label


@dataclass
class PairwiseJudgement(Judgement):
    """Two candidates compared metric-by-metric."""

    candidate_a_id: str | None = None
    candidate_b_id: str | None = None
    preference: dict[str, str] | None = None  # {metric: 'a' | 'b' | 'tie'}
    winner: str | None = None  # derived from preference
