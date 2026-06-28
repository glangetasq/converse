"""LinkedIn profile ingestor.

`parse` turns a parsed profile payload into a source document (person deduped on
linkedin_url). `chunk` — turning that document into atomic memories — is scaffolded
but not yet implemented.
"""

from __future__ import annotations

import json
from typing import Any

from .base import MemoryDraft, ParsedSource, PersonIdentity, SourceIngestor


def _as_dict(result: Any) -> dict[str, Any]:
    """The parser sometimes emits the profile as a JSON string; normalize to a dict."""
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, dict):
        raise ValueError("LinkedIn profile result must be an object or JSON object string.")
    return result


def _full_name(profile: dict[str, Any]) -> str | None:
    parts = [str(profile.get("first_name") or "").strip(), str(profile.get("last_name") or "").strip()]
    name = " ".join(part for part in parts if part)
    return name or None


def _raw_text(profile: dict[str, Any]) -> str:
    """Flattened text for debugging / future hybrid full-text search."""
    chunks: list[str] = []
    for key in ("headline", "location", "about"):
        value = profile.get(key)
        if value:
            chunks.append(str(value).strip())
    for exp in profile.get("experience") or []:
        if isinstance(exp, dict):
            line = " — ".join(
                str(exp[k]).strip()
                for k in ("job_title", "company", "about")
                if exp.get(k)
            )
            if line:
                chunks.append(line)
    for edu in profile.get("education") or []:
        if isinstance(edu, dict):
            line = " — ".join(
                str(edu[k]).strip()
                for k in ("university_school_name", "degree_domain", "last_year_attended")
                if edu.get(k)
            )
            if line:
                chunks.append(line)
    return "\n".join(chunks)


class LinkedInProfileIngestor(SourceIngestor):
    parser_id = "linkedin-profile"
    kind = "linkedin_profile"
    source = "linkedin"

    def parse(self, result: Any, source_url: str | None) -> ParsedSource:
        profile = _as_dict(result)
        return ParsedSource(
            kind=self.kind,
            source=self.source,
            content=profile,
            source_url=source_url,
            raw_text=_raw_text(profile),
            person=PersonIdentity(full_name=_full_name(profile), linkedin_url=source_url),
        )

    def chunk(self, document: dict[str, Any]) -> list[MemoryDraft]:
        # TODO: slice document["content"] (headline / about / experience / education)
        # into atomic, self-contained MemoryDrafts. Scaffolded only — returns no
        # memories yet, so the atomize/reprocess plumbing runs end-to-end as a no-op.
        return []
