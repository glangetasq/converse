from __future__ import annotations

from abc import ABC, abstractmethod
from string import Template
from typing import Any

from ..utils import render_thread
from .context import PromptContext


class Augmentor(ABC):
    name: str

    @abstractmethod
    async def augment(self, context: PromptContext, prompt: str) -> str: ...

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

    async def build(self, context: PromptContext) -> str:
        # template placeholders: $sender_name, $recipient_name, $thread
        prompt = self.template.substitute(
            sender_name=context.sender_name,
            recipient_name=context.recipient_name,
            thread=render_thread(context.thread),
        )
        if self.augment is not None:
            prompt = await self.augment.augment(context, prompt)
        return prompt

    def spec(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "augment": self.augment.spec() if self.augment else None,
        }
