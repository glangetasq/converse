"""no_rag and full_rag share one template + GenConfig, differing only by whether
the SuggestionPromptBuilder carries a RagAugmentor, so RAG is the sole A/B variable."""

from __future__ import annotations

from string import Template

from ...prompting import SuggestionPromptBuilder  # noqa: F401 — used by the arm builders below
from ..framework.arm import Arm
from ..framework.judges import Judge
from .assets import LIBRARY, SUGGEST, SUGGEST_VERSION

DEFAULT_MODEL = "gpt-5.4-nano"   # keep the eval's current model (D5)


def suggest_template() -> Template:
    """The base (no-RAG) suggestion prompt, shared by both arms."""
    return LIBRARY.load(SUGGEST, SUGGEST_VERSION).as_template(
        {"sender_name", "recipient_name", "thread"}
    )


def no_rag_arm(model_name: str = DEFAULT_MODEL) -> Arm:
    # SuggestionPromptBuilder(suggest_template(), SUGGEST_VERSION)
    raise NotImplementedError


def full_rag_arm(model_name: str = DEFAULT_MODEL) -> Arm:
    # SuggestionPromptBuilder(suggest_template(), SUGGEST_VERSION, RagAugmentor(RetrievalConfig()))
    raise NotImplementedError


def linkedin_judge(model_name: str = DEFAULT_MODEL) -> Judge:
    raise NotImplementedError
