from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from string import Template
from typing import Any, Sequence

from ..loggers import api_logger
from ..utils import fingerprint as _fingerprint
from ..utils import render_thread
from .context import PromptContext


@dataclass(frozen=True)
class BuiltPrompt:
    prompt: str
    evidence: str | None = None  # facts an augmentor injected, surfaced so the judge can see them too
    provenance: dict[str, Any] = field(default_factory=dict)  # fact ids, flags, errors — for tracing, not the judge


class Augmentor(ABC):
    name: str

    @abstractmethod
    async def augment(self, context: PromptContext, prompt: str) -> tuple[str, str | None, dict[str, Any]]:
        """Return (prompt, evidence block or None, provenance)."""

    def spec(self) -> dict[str, Any]:
        return {"name": self.name}


class CompositeAugmentor(Augmentor):
    """Chain augmentors: evidence concatenates, provenance merges. Is itself an
    Augmentor, so it fills the builder's single augment slot.

    `degrade_on_error` (one bool, or one per augmentor): when a child raises and its
    flag is set, skip it (prompt unchanged) and record the error under
    provenance['errors'][name] instead of failing; otherwise the error propagates."""

    name = "composite"

    def __init__(
        self,
        augmentors: Sequence[Augmentor],
        *,
        degrade_on_error: bool | Sequence[bool] = False,
    ) -> None:
        self.augmentors = list(augmentors)
        if isinstance(degrade_on_error, bool):
            self.degrade_on_error = [degrade_on_error] * len(self.augmentors)
        else:
            self.degrade_on_error = list(degrade_on_error)
            if len(self.degrade_on_error) != len(self.augmentors):
                raise ValueError("degrade_on_error sequence must match augmentors length")

    async def augment(self, context: PromptContext, prompt: str) -> tuple[str, str | None, dict[str, Any]]:
        evidence: str | None = None
        provenance: dict[str, Any] = {}
        errors: dict[str, str] = {}
        for augmentor, degrade in zip(self.augmentors, self.degrade_on_error):
            try:
                prompt, block, prov = await augmentor.augment(context, prompt)
            except Exception as error:  # noqa: BLE001
                if not degrade:
                    raise
                api_logger.warning("Augmentor %s failed, skipping: %s", augmentor.name, error)
                errors[augmentor.name] = str(error)
                continue
            if block:
                evidence = block if evidence is None else f"{evidence}\n\n{block}"
            provenance.update(prov)
        if errors:
            provenance["errors"] = errors
        return prompt, evidence, provenance

    def spec(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "augmentors": [augmentor.spec() for augmentor in self.augmentors],
            "degrade_on_error": self.degrade_on_error,
        }


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
