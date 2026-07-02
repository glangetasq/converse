from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from string import Template
from typing import Any

from ..utils import fingerprint as _fingerprint
from ..utils import render_thread
from .context import PromptContext


@dataclass(frozen=True)
class BuiltPrompt:
    prompt: str
    evidence: str | None = None  # facts an augmentor injected, surfaced so the judge can see them too


class Augmentor(ABC):
    name: str

    @abstractmethod
    async def augment(self, context: PromptContext, prompt: str) -> tuple[str, str | None]:
        """Return the augmented prompt and the evidence block it injected (None if nothing)."""

    def spec(self) -> dict[str, Any]:
        return {"name": self.name}


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
        prompt, evidence = await self.augment.augment(context, prompt)
        return BuiltPrompt(prompt, evidence)

    def spec(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "fingerprint": _fingerprint(self.template.template),
            "augment": self.augment.spec() if self.augment else None,
        }
