"""Prompt assembly for live (non-eval) follow-up generation: latest suggest asset +
RAG facts + the sender's free-text context. Retrieval failure degrades to the
un-augmented prompt instead of failing the request."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..assets import ASSETS_DIR, AssetLibrary
from ..loggers import api_logger
from ..retrieval import DEFAULT_CONFIG
from .builder import SuggestionPromptBuilder
from .context import Thread
from .rag import RagAugmentor

LIBRARY = AssetLibrary(ASSETS_DIR)
SUGGEST = "prompts/linkedin/suggest"
SUGGEST_FIELDS = ("sender_name", "recipient_name", "thread")
ADDITIONAL_CONTEXT_HEADER = "Additional context from the sender (use it to steer this reply):"


@dataclass(frozen=True)
class LiveContext:
    """Satisfies PromptContext for a request-supplied thread."""

    thread: Thread
    sender_name: str
    recipient_name: str
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LivePrompt:
    prompt: str
    evidence: str | None
    version: str
    rag_error: str | None = None


def suggestion_builder(version: str | None = None) -> SuggestionPromptBuilder:
    version = version or LIBRARY.latest_version(SUGGEST)
    template = LIBRARY.load_template(SUGGEST, version, fields=SUGGEST_FIELDS)
    return SuggestionPromptBuilder(template, version)


async def build_live_prompt(
    context: LiveContext,
    additional_context: str | None = None,
    *,
    version: str | None = None,
) -> LivePrompt:
    builder = suggestion_builder(version)
    built = await builder.build(context)
    prompt, evidence, rag_error = built.prompt, None, None

    try:
        prompt, evidence = await RagAugmentor(DEFAULT_CONFIG).augment(context, built.prompt)
    except Exception as error:  # noqa: BLE001 — degrade to no-RAG rather than fail the request
        rag_error = str(error)
        api_logger.warning("RAG augmentation failed, generating without facts: %s", rag_error)

    extra = (additional_context or "").strip()
    if extra:
        prompt = f"{prompt}\n\n{ADDITIONAL_CONTEXT_HEADER}\n{extra}"

    return LivePrompt(prompt, evidence, builder.version, rag_error)
