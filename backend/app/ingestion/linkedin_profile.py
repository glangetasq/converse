"""LinkedIn profile ingestor.

`parse` turns a parsed profile payload into a source document (person deduped on
linkedin_url). `chunk` — turning that document into atomic memories — is scaffolded
but not yet implemented.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

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
            line = " — ".join(str(exp[k]).strip() for k in ("job_title", "company", "about") if exp.get(k))
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


def _clean(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _handle_from_url(source_url: str | None) -> str | None:
    if not source_url:
        return None
    slug = urlparse(source_url).path.rstrip("/").rsplit("/", 1)[-1]
    words = [word for word in slug.split("-") if word and not word.isdigit()]
    return " ".join(word.capitalize() for word in words) or None


def _subject(profile: dict[str, Any], source_url: str | None) -> str:
    """Name to anchor every memory on, with graceful fallbacks for a nameless scrape."""
    return _full_name(profile) or _handle_from_url(source_url) or "This LinkedIn contact"


def _role_context(experience: dict[str, Any]) -> str:
    title = _clean(experience.get("job_title"))
    company = _clean(experience.get("company"))
    if title and company:
        return f"{title} at {company}"
    return title or company or ""


def _current_experience(profile: dict[str, Any]) -> dict[str, Any] | None:
    for experience in profile.get("experience") or []:
        if isinstance(experience, dict) and experience.get("is_actively_working"):
            return experience
    return None


def _headline_memory(subject: str, profile: dict[str, Any]) -> str | None:
    headline = _clean(profile.get("headline"))
    location = _clean(profile.get("location"))
    current = _current_experience(profile)
    role = _role_context(current) if current else ""
    if not (headline or location or role):
        return None
    parts = [f"{subject} — {headline}" if headline else subject]
    if role:
        years = current.get("time_employed_years")
        parts.append(f"Currently {role}" + (f" ({years} yrs)" if years else ""))
    if location:
        parts.append(f"Based in {location}")
    return ". ".join(parts) + "."


def _about_memory(subject: str, profile: dict[str, Any]) -> str | None:
    about = _clean(profile.get("about"))
    return f"{subject}: {about}" if about else None


def _role_memory(subject: str, experience: dict[str, Any]) -> str | None:
    title = _clean(experience.get("job_title"))
    company = _clean(experience.get("company"))
    if not (title or company):
        return None
    verb = "currently works" if experience.get("is_actively_working") else "previously worked"
    where = f" as {title}" + (f" at {company}" if company else "") if title else f" at {company}"
    years = experience.get("time_employed_years")
    duration = f" ({years} yrs)" if years else ""
    return f"{subject} {verb}{where}{duration}."


def _role_highlights_memory(subject: str, experience: dict[str, Any]) -> str | None:
    about = _clean(experience.get("about"))
    if not about:
        return None
    context = _role_context(experience)
    return f"{subject} ({context}): {about}" if context else f"{subject}: {about}"


def _education_memory(subject: str, education: dict[str, Any]) -> str | None:
    school = _clean(education.get("university_school_name"))
    if not school:
        return None
    degree = _clean(education.get("degree_domain"))
    year = education.get("last_year_attended")
    studied = f" studied {degree} at" if degree else " attended"
    graduated = f" (until {year})" if year else ""
    return f"{subject}{studied} {school}{graduated}."


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
        profile = _as_dict(document["content"])
        subject = _subject(profile, document.get("source_url"))
        drafts: list[MemoryDraft] = []

        def add(memory_type: str, content: str | None) -> None:
            if content:
                drafts.append(MemoryDraft(memory_type=memory_type, content=content))

        add("headline", _headline_memory(subject, profile))
        add("about", _about_memory(subject, profile))
        for experience in profile.get("experience") or []:
            if not isinstance(experience, dict):
                continue
            role_type = "current_role" if experience.get("is_actively_working") else "past_role"
            add(role_type, _role_memory(subject, experience))
            add("role_highlights", _role_highlights_memory(subject, experience))
        for education in profile.get("education") or []:
            if isinstance(education, dict):
                add("education", _education_memory(subject, education))

        return drafts
