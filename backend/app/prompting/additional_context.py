from __future__ import annotations

from typing import Any

from .builder import Augmentor
from .context import PromptContext

HEADER = "Additional context from the sender (use it to steer this reply):"


class AdditionalContextAugmentor(Augmentor):
    """Appends the sender's free-text context, read from `context.meta['additional_context']`.
    Per-request text rides in meta (like RagAugmentor's ids), so one instance serves any
    request. Not evidence — it is instruction, not retrieved fact — so evidence stays None."""

    name = "additional_context"

    async def augment(self, context: PromptContext, prompt: str) -> tuple[str, str | None, dict[str, Any]]:
        extra = str(context.meta.get("additional_context") or "").strip()
        if not extra:
            return prompt, None, {}
        return f"{prompt}\n\n{HEADER}\n{extra}", None, {"additional_context": True}
