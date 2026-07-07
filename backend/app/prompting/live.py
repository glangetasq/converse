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
    fact_ids: tuple[str, ...] = ()
    spec: Mapping[str, Any] = field(default_factory=dict)


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
    augmentor = RagAugmentor(DEFAULT_CONFIG)
    prompt, evidence, rag_error = built.prompt, None, None
    fact_ids: list[str] = []

    try:
        prompt, evidence, facts = await augmentor.augment_with_facts(context, built.prompt)
        for retrieved in facts:
            fact_ids.append(retrieved.fact.id)
            if retrieved.matched is not None:
                fact_ids.append(retrieved.matched.id)
    except Exception as error:  # noqa: BLE001 — degrade to no-RAG rather than fail the request
        rag_error = str(error)
        api_logger.warning("RAG augmentation failed, generating without facts: %s", rag_error)

    extra = (additional_context or "").strip()
    if extra:
        prompt = f"{prompt}\n\n{ADDITIONAL_CONTEXT_HEADER}\n{extra}"

    # spec reflects what actually shaped the prompt: augment is None when RAG failed
    spec = {**builder.spec(), "augment": augmentor.spec() if rag_error is None else None}
    return LivePrompt(prompt, evidence, builder.version, rag_error, tuple(fact_ids), spec)
