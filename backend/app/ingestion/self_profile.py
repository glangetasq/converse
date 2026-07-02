"""Self-profile ingestor.

The user's own facts (goals, motivation, experience, projects, skills) authored as
a single markdown document. Unlike a scraped LinkedIn profile, this is hand-written
and not reproducible, so the markdown is the curated source of truth — stored
verbatim in `source_documents` and sliced into atomic `memory_items` here.

The markdown contract is deliberately tiny so chunking stays a pure split with NO
inference (the curation already happened when the facts were authored):

  * `#  Title`         -> document title (provenance only, not a memory)
  * `## Section`       -> selects the memory_type for everything beneath it
  * `- bullet`         -> one atomic, self-contained memory
  * a plain paragraph  -> one atomic memory (blank-line separated)

Every memory is a self-document (person_id NULL); the owning user comes from the
ingest call, so these retrieve as "facts about the sender" alongside a recipient's
person-scoped facts.
"""

from __future__ import annotations

import json
import re
from typing import Any

# `<!-- ... -->` blocks (e.g. an authoring guide at the top of the file) are notes,
# not facts — stripped before parsing so they never leak into memories.
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

from .base import MemoryDraft, ParsedSource, SourceIngestor

# Section heading (lowercased, substring) -> memory_type. First match wins, so more
# specific keywords come before the ones they contain ("education" before the
# "experience" that "work experience" would also match).
_HEADING_TYPES: list[tuple[str, str]] = [
    ("headline", "user.headline"),
    ("goal", "user.goal"),
    ("moving to tech", "user.constraint"),
    ("why", "user.constraint"),
    ("motivation", "user.constraint"),
    ("looking for", "user.constraint"),
    ("education", "user.education"),
    ("experience", "user.experience"),
    ("project", "user.project"),
    ("skill", "user.skill"),
]
_FALLBACK_TYPE = "user.note"

_BULLET_MARKERS = ("- ", "* ", "+ ")


def _memory_type_for_heading(heading: str) -> str:
    lowered = heading.strip().lower()
    for keyword, memory_type in _HEADING_TYPES:
        if keyword in lowered:
            return memory_type
    return _FALLBACK_TYPE


def _strip_bullet(line: str) -> str | None:
    """Return the text after a bullet marker, or None if the line isn't a bullet."""
    for marker in _BULLET_MARKERS:
        if line.startswith(marker):
            return line[len(marker) :].strip()
    return None


def parse_self_profile_markdown(text: str) -> tuple[str | None, list[MemoryDraft]]:
    """Split authored self-profile markdown into a title + atomic memory drafts.

    Pure and deterministic: each bullet (or blank-line-separated paragraph) under a
    `##` section becomes one MemoryDraft typed by that section. Content before the
    first section, and wrapped continuation lines, are handled gracefully.
    """
    text = _HTML_COMMENT.sub("", text)
    title: str | None = None
    current_type: str | None = None
    buffer: list[str] = []
    drafts: list[MemoryDraft] = []

    def flush() -> None:
        nonlocal buffer
        if buffer and current_type:
            content = " ".join(buffer).strip()
            if content:
                drafts.append(MemoryDraft(memory_type=current_type, content=content))
        buffer = []

    for raw_line in text.splitlines():
        stripped = raw_line.strip()

        if stripped.startswith("## "):
            flush()
            current_type = _memory_type_for_heading(stripped[3:])
            continue
        if stripped.startswith("# "):
            flush()
            if title is None:
                title = stripped[2:].strip()
            continue
        if not stripped:
            flush()
            continue

        bullet = _strip_bullet(stripped)
        if bullet is not None:
            flush()  # one memory per bullet
            buffer.append(bullet)
        else:
            buffer.append(stripped)  # paragraph text or a wrapped bullet continuation

    flush()
    return title, drafts


def _as_markdown(result: Any) -> str:
    """Accept a raw markdown string or a {'markdown': ...} payload; return the text."""
    if isinstance(result, str):
        return result
    if isinstance(result, dict) and isinstance(result.get("markdown"), str):
        return result["markdown"]
    raise ValueError("Self-profile result must be markdown text or a {'markdown': ...} object.")


def _content(document_content: Any) -> dict[str, Any]:
    if isinstance(document_content, str):
        return json.loads(document_content)
    if isinstance(document_content, dict):
        return document_content
    raise ValueError("Self-profile source document content must be an object or JSON string.")


class SelfProfileIngestor(SourceIngestor):
    parser_id = "self-profile"
    kind = "self_profile"
    source = "manual"

    def parse(self, result: Any, source_url: str | None) -> ParsedSource:
        markdown = _as_markdown(result)
        title, _ = parse_self_profile_markdown(markdown)
        return ParsedSource(
            kind=self.kind,
            source=self.source,
            content={"markdown": markdown, "title": title},
            source_url=source_url,
            raw_text=markdown,
            person=None,  # self-document: person_id stays NULL
        )

    def chunk(self, document: dict[str, Any]) -> list[MemoryDraft]:
        markdown = _content(document["content"]).get("markdown", "")
        _title, drafts = parse_self_profile_markdown(markdown)
        return drafts
