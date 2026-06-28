"""Source ingestion: the class hierarchy shared by every source type.

A `SourceIngestor` owns the two stages for one source type:

  1. ingest:  raw payload  -> source_documents   (parse + persist, deduped)
  2. atomize: source document -> memory_items     (chunk + embed + persist, deduped)

Per-source knowledge lives in the subclass (`parse`, `chunk`); everything shared
— person resolution, content hashing, the deduplicated writes, embedding — lives
here so adding a new source type is just a subclass with two methods.

Transaction expectations differ by stage and are documented per method:
  * `ingest`  assumes the caller already opened a transaction (the request handler).
  * `atomize` opens its OWN short transaction around the insert, and must therefore
    be called WITHOUT an outer transaction, so the embedding network call happens
    outside any open transaction.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from ..llm.embeddings import get_embedder
from ..persons_service import find_or_create_person


@dataclass
class PersonIdentity:
    """Identity fields used to resolve (dedupe) or create a person."""

    full_name: str | None = None
    linkedin_url: str | None = None
    email: str | None = None


@dataclass
class ParsedSource:
    """Normalized output of a source-type parser, ready to persist."""

    kind: str                       # source_documents.kind
    source: str                     # source_documents.source
    content: dict[str, Any]         # parser JSON verbatim -> content jsonb
    source_url: str | None = None
    raw_text: str | None = None
    person: PersonIdentity | None = None  # None => a self-document (person_id NULL)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestResult:
    status: str                     # 'ingested' | 'duplicate'
    source_document_id: str | None
    person_id: str | None


@dataclass
class MemoryDraft:
    """A single atomic memory before hashing/embedding/persistence.

    `content` is a self-contained, decontextualized statement — it is embedded and
    retrieved on its own, so it should carry the subject's name/company context.
    """

    memory_type: str
    content: str


def content_hash(content: dict[str, Any]) -> str:
    """Stable hash of parser content, so identical re-scrapes dedupe."""
    canonical = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def text_hash(text: str) -> str:
    """Stable hash of a memory's text, for the (user_id, content_hash) dedupe."""
    return hashlib.sha256(text.strip().casefold().encode("utf-8")).hexdigest()


def _vector_literal(vector: list[float]) -> str:
    """pgvector text form '[1,2,3]', inserted with an explicit ::vector cast."""
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


class SourceIngestor(ABC):
    """One source type's ingest (raw) + atomize (memories) pipeline."""

    parser_id: str   # live dispatch key (frontend parse_dump payload), e.g. "linkedin-profile"
    kind: str        # source_documents.kind; reprocess dispatch key, e.g. "linkedin_profile"
    source: str      # source_documents.source / memory_items.source, e.g. "linkedin"

    # --- per-source knowledge (subclass implements) -----------------------------
    @abstractmethod
    def parse(self, result: Any, source_url: str | None) -> ParsedSource:
        """Normalize a raw parser payload into a ParsedSource."""

    @abstractmethod
    def chunk(self, document: dict[str, Any]) -> list[MemoryDraft]:
        """Slice a persisted source_documents row into atomic memory drafts."""

    # --- shared pipeline (concrete) ---------------------------------------------
    async def ingest(
        self,
        conn: AsyncConnection,
        user_id: str,
        *,
        result: Any,
        source_url: str | None,
    ) -> IngestResult:
        """Stage 1. Parse + persist the raw document. Caller owns the transaction."""
        return await self._persist_document(conn, user_id, self.parse(result, source_url))

    async def atomize(
        self,
        conn: AsyncConnection,
        document: dict[str, Any],
    ) -> list[str]:
        """Stage 2. Chunk + embed + persist memories. Opens its own insert transaction.

        The memory's owner is taken from the document, so this needs no user_id.
        Returns the ids of newly inserted memory_items (duplicates skipped).
        """
        drafts = self.chunk(document)
        if not drafts:
            return []

        vectors = await get_embedder().embed([draft.content for draft in drafts])

        async with conn.transaction():
            return await self._persist_memories(conn, document, drafts, vectors)

    async def _persist_document(
        self,
        conn: AsyncConnection,
        user_id: str,
        parsed: ParsedSource,
    ) -> IngestResult:
        """Resolve the person and write the source document, skipping exact duplicates."""
        person_id: str | None = None
        if parsed.person is not None:
            person = await find_or_create_person(
                conn,
                user_id,
                source=parsed.source,
                full_name=parsed.person.full_name,
                linkedin_url=parsed.person.linkedin_url,
                email=parsed.person.email,
            )
            person_id = str(person["id"])

        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO source_documents (
                  user_id, person_id, kind, source, source_url, content, raw_text, content_hash
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, content_hash) DO NOTHING
                RETURNING id
                """,
                (
                    user_id,
                    person_id,
                    parsed.kind,
                    parsed.source,
                    parsed.source_url,
                    Jsonb(parsed.content),
                    parsed.raw_text,
                    content_hash(parsed.content),
                ),
            )
            row = await cur.fetchone()

        if row is None:
            return IngestResult(status="duplicate", source_document_id=None, person_id=person_id)

        return IngestResult(status="ingested", source_document_id=str(row["id"]), person_id=person_id)

    async def _persist_memories(
        self,
        conn: AsyncConnection,
        document: dict[str, Any],
        drafts: list[MemoryDraft],
        vectors: list[list[float]],
    ) -> list[str]:
        """Insert memory_items for one document, deduped on (user_id, content_hash).

        The owner (user_id) and provenance are taken from the document row.
        Must run inside a transaction (atomize provides one).
        """
        inserted: list[str] = []
        user_id = document["user_id"]
        person_id = document.get("person_id")
        source_document_id = document["id"]

        async with conn.cursor() as cur:
            for draft, vector in zip(drafts, vectors):
                await cur.execute(
                    """
                    INSERT INTO memory_items (
                      user_id, person_id, source_document_id,
                      memory_type, content, content_hash, source, embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT (user_id, content_hash) DO NOTHING
                    RETURNING id
                    """,
                    (
                        user_id,
                        person_id,
                        source_document_id,
                        draft.memory_type,
                        draft.content,
                        text_hash(draft.content),
                        self.source,
                        _vector_literal(vector),
                    ),
                )
                row = await cur.fetchone()
                if row is not None:
                    inserted.append(str(row["id"]))

        return inserted
