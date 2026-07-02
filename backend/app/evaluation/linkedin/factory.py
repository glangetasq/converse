"""Build the pieces of a LinkedIn experiment. Every knob is a keyword with a default,
so an A/B is `[no_rag(), full_rag()]` and a variant is `no_rag(suggest="v2")`. A
version left None resolves to the latest asset on disk (AssetLibrary.latest_version)."""

from __future__ import annotations

from typing import Sequence

from ...assets import ASSETS_DIR, AssetLibrary
from ...llm import GenConfig, get_client, get_genconfig
from ...prompting import RagAugmentor, SuggestionPromptBuilder
from ...retrieval import DEFAULT_CONFIG, RetrievalConfig
from ...utils import render_thread
from ..framework import (
    Arm,
    Candidate,
    Case,
    Judge,
    JudgePromptBuilder,
    PairwiseJudge,
    PointwiseJudge,
    Scorecard,
)

LIBRARY = AssetLibrary(ASSETS_DIR)
SUGGEST = "prompts/linkedin/suggest"
JUDGE = "prompts/linkedin/judge"  # actual asset at JUDGE/<mode>/<version>
SCORECARD = "scorecards/linkedin"

DEFAULT_MODEL = "gpt-5.4-nano"

_SUGGEST_FIELDS = ("sender_name", "recipient_name", "thread")
_JUDGE_FIELDS = {
    "pointwise": (
        "sender_name",
        "recipient_name",
        "past_conversation",
        "actual_next_message",
        "suggested_next_message",
        "available_facts",
        "scorecard",
    ),
    "pairwise": (
        "sender_name",
        "recipient_name",
        "past_conversation",
        "actual_next_message",
        "suggestion_a",
        "facts_a",
        "suggestion_b",
        "facts_b",
        "scorecard",
    ),
}
_JUDGE_KINDS = {"pointwise": PointwiseJudge, "pairwise": PairwiseJudge}


def scorecard(version: str | None = None) -> Scorecard:
    version = version or LIBRARY.latest_version(SCORECARD)
    return Scorecard.from_markdown(LIBRARY.load(SCORECARD, version).text, version=version)


def arm(
    name: str,
    *,
    suggest: str | None = None,
    model: str = DEFAULT_MODEL,
    gen: GenConfig | None = None,
    rag: RetrievalConfig | None = None,  # None -> no RAG
) -> Arm:
    suggest = suggest or LIBRARY.latest_version(SUGGEST)
    template = LIBRARY.load_template(SUGGEST, suggest, fields=_SUGGEST_FIELDS)
    augment = RagAugmentor(rag) if rag is not None else None
    builder = SuggestionPromptBuilder(template, suggest, augment)
    return Arm(name, builder, get_client(model), gen or get_genconfig(model))


def no_rag(**kwargs) -> Arm:
    return arm("no_rag", **kwargs)


def full_rag(*, rag: RetrievalConfig | None = None, **kwargs) -> Arm:
    return arm("full_rag", rag=rag or DEFAULT_CONFIG, **kwargs)


class _JudgePrompt(JudgePromptBuilder):
    def __init__(self, mode: str, version: str, scorecard_version: str) -> None:
        self._mode = mode
        self._asset = LIBRARY.load(f"{JUDGE}/{mode}", version)
        self._template = self._asset.as_template(_JUDGE_FIELDS[mode])
        self._scorecard = LIBRARY.load(SCORECARD, scorecard_version).text

    def build(self, case: Case, candidates: Sequence[Candidate], scorecard: Scorecard) -> str:
        fields = {
            "sender_name": case.sender_name,
            "recipient_name": case.recipient_name,
            "past_conversation": render_thread(case.thread) or "(no prior conversation)",
            "actual_next_message": case.ground_truth or "",
            "scorecard": self._scorecard,
        }
        if self._mode == "pointwise":
            fields["suggested_next_message"] = candidates[0].text
            fields["available_facts"] = candidates[0].evidence or "(none)"
        else:
            fields["suggestion_a"] = candidates[0].text
            fields["facts_a"] = candidates[0].evidence or "(none)"
            fields["suggestion_b"] = candidates[1].text
            fields["facts_b"] = candidates[1].evidence or "(none)"
        return self._template.substitute(fields)

    def spec(self) -> dict:
        return {"builder": "LinkedInJudgePrompt", "mode": self._mode, **self._asset.spec()}


def judge(
    *,
    mode: str = "pointwise",  # "pairwise" for A/B of two arms
    version: str | None = None,
    scorecard_version: str | None = None,
    model: str = DEFAULT_MODEL,
    gen: GenConfig | None = None,
) -> Judge:
    version = version or LIBRARY.latest_version(f"{JUDGE}/{mode}")
    scorecard_version = scorecard_version or LIBRARY.latest_version(SCORECARD)
    prompt = _JudgePrompt(mode, version, scorecard_version)
    return _JUDGE_KINDS[mode](
        f"linkedin_{mode}",
        scorecard(scorecard_version),
        get_client(model),
        gen or get_genconfig(model),
        prompt,
    )
