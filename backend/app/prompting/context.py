from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

Thread = Sequence[Mapping[str, Any]]  # each item: {body, sent_time, sender_name}


class PromptContext(Protocol):
    """Structural input a builder needs. The eval's Case satisfies it, so prompting
    never imports evaluation. Retrieval ids live in meta under "user_id"/"person_id"."""

    thread: Thread
    sender_name: str
    recipient_name: str
    meta: Mapping[str, Any]
