from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from string import Template
from typing import Any, Sequence

from ..utils import fingerprint as _fingerprint
from ..utils import render_thread
from .context import PromptContext


@dataclass(frozen=True)
class BuiltPrompt:
    prompt: str
    evidence: str | None = None  # facts an augmentor injected, surfaced so the judge can see them too
    provenance: dict[str, Any] = field(default_factory=dict)  # machine-readable trace: fact ids, flags, errors


class Augmentor(ABC):
    name: str

    @abstractmethod
    async def augment(self, context: PromptContext, prompt: str) -> tuple[str, str | None, dict[str, Any]]:
        """Return (augmented prompt, evidence block or None, provenance dict).
        Evidence is judge-facing text; provenance is a machine-readable trace."""

    def spec(self) -> dict[str, Any]:
        return {"name": self.name}


class CompositeAugmentor(Augmentor):
    """Runs augmentors in sequence, threading the prompt through each. Evidence blocks
    concatenate; provenance dicts merge. Being an Augmentor itself, it slots into a
    builder's single `augment` slot unchanged."""

    name = "composite"

    def __init__(self, augmentors: Sequence[Augmentor]) -> None:
        self.augmentors = list(augmentors)

    async def augment(self, context: PromptContext, prompt: str) -> tuple[str, str | None, dict[str, Any]]:
        evidence: str | None = None
        provenance: dict[str, Any] = {}
        for augmentor in self.augmentors:
            prompt, block, prov = await augmentor.augment(context, prompt)
            if block:
                evidence = block if evidence is None else f"{evidence}\n\n{block}"
            provenance.update(prov)
        return prompt, evidence, provenance

    def spec(self) -> dict[str, Any]:
        return {"name": self.name, "augmentors": [augmentor.spec() for augmentor in self.augmentors]}


class SuggestionPromptBuilder:
    """Renders a versioned template, then optionally runs it through one Augmentor.
    no_rag vs full_rag differ only by whether `augment` is set — the A/B variable."""

    def __init__(
        self,
        template: Template,
        version: str,
        augment: Augmentor | None = None,
    ) -> None:
        self.template = template
        self.version = version
        self.augment = augment

    async def build(self, context: PromptContext) -> BuiltPrompt:
        # template placeholders: $sender_name, $recipient_name, $thread
        prompt = self.template.substitute(
            sender_name=context.sender_name,
            recipient_name=context.recipient_name,
            thread=render_thread(context.thread),
        )
        if self.augment is None:
            return BuiltPrompt(prompt)
        prompt, evidence, provenance = await self.augment.augment(context, prompt)
        return BuiltPrompt(prompt, evidence, provenance)

    def spec(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "fingerprint": _fingerprint(self.template.template),
            "augment": self.augment.spec() if self.augment else None,
        }
