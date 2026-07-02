from __future__ import annotations

from typing import Any

from ..retrieval import RetrievalConfig, RetrievedFact, retrieve_facts_for_thread
from .builder import Augmentor
from .context import PromptContext

FACTS_HEADER = "Relevant background:"


def _bullets(header: str, contents: list[str]) -> str:
    return header + "\n" + "\n".join(f"- {content}" for content in contents)


class RagAugmentor(Augmentor):
    """Retrieves facts for the thread and appends a formatted block to the prompt."""

    name = "rag"

    def __init__(self, config: RetrievalConfig | None = None) -> None:
        self.config = config or RetrievalConfig()

    async def augment(self, context: PromptContext, prompt: str) -> tuple[str, str | None]:
        facts = await self._retrieve(context)
        if not facts:
            return prompt, None
        block = self._format(facts, context.sender_name, context.recipient_name)
        return f"{prompt}\n\n{FACTS_HEADER}\n{block}", block

    async def _retrieve(self, context: PromptContext) -> list[RetrievedFact]:
        missing = [key for key in ("user_id", "person_id") if key not in context.meta]
        if missing:
            raise KeyError(f"RagAugmentor needs {missing} in context.meta")
        return await retrieve_facts_for_thread(
            context.meta["user_id"],
            context.meta["person_id"],
            context.thread,
            config=self.config,
        )

    @staticmethod
    def _format(facts: list[RetrievedFact], sender_name: str, recipient_name: str) -> str:
        # about_you facts are the sender's, about_them the recipient's; shared_ground
        # carries the sender's fact in .fact and the recipient's in .matched.
        about_sender, about_recipient, shared = [], [], []
        for rf in facts:
            if rf.label == "shared_ground":
                shared.append(rf)
            elif rf.label == "about_you":
                about_sender.append(rf.fact.content)
            else:
                about_recipient.append(rf.fact.content)

        sections: list[str] = []
        if about_sender:
            sections.append(_bullets(f"About {sender_name}:", about_sender))
        if about_recipient:
            sections.append(_bullets(f"About {recipient_name}:", about_recipient))
        if shared:
            # blank line between pairs so each (sender, recipient) tuple reads as a unit
            pairs = [f"- {sender_name}: {rf.fact.content}\n  {recipient_name}: {rf.matched.content}" for rf in shared]
            sections.append("Shared ground:\n" + "\n\n".join(pairs))
        return "\n\n".join(sections)

    def spec(self) -> dict[str, Any]:
        return {"name": self.name, "k": self.config.k}
