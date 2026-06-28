"""Ingestion: turn parsed artifacts into source_documents (and, later, memory_items).

Each source type is a `SourceIngestor` instance, registered under both its
`parser_id` (live dispatch from parse_dump) and its `kind` (reprocess dispatch
from a stored source_documents row).
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection

from .base import IngestResult, MemoryDraft, ParsedSource, SourceIngestor
from .linkedin_profile import LinkedInProfileIngestor

_INGESTORS: list[SourceIngestor] = [
    LinkedInProfileIngestor(),
]

_BY_PARSER_ID: dict[str, SourceIngestor] = {ing.parser_id: ing for ing in _INGESTORS}
_BY_KIND: dict[str, SourceIngestor] = {ing.kind: ing for ing in _INGESTORS}


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def get_by_parser_id(parser_id: str | None) -> SourceIngestor | None:
    return _BY_PARSER_ID.get(_norm(parser_id))


def get_by_kind(kind: str | None) -> SourceIngestor | None:
    return _BY_KIND.get(_norm(kind))


def supports(parser_id: str | None) -> bool:
    return _norm(parser_id) in _BY_PARSER_ID


def kinds() -> list[str]:
    """Registered source kinds — used for the reprocess CLI's --source choices."""
    return list(_BY_KIND)


async def ingest(
    conn: AsyncConnection,
    user_id: str,
    *,
    parser_id: str | None,
    result: Any,
    source_url: str | None,
) -> IngestResult | None:
    """Dispatch a parsed payload to its source-type ingestor by parser_id.

    Returns None when no ingestor is registered for the parser_id.
    """
    ingestor = get_by_parser_id(parser_id)
    if ingestor is None:
        return None
    return await ingestor.ingest(conn, user_id, result=result, source_url=source_url)


__all__ = [
    "IngestResult",
    "MemoryDraft",
    "ParsedSource",
    "SourceIngestor",
    "ingest",
    "supports",
    "kinds",
    "get_by_kind",
    "get_by_parser_id",
]
