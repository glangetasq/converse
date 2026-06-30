"""Rebuild memory_items from stored source_documents.

Chunking is version-dependent: when a source type's `chunk()` changes, the derived
memories are stale and must be rebuilt from the raw documents (which are the source
of truth). This script wipes the memories derived from the selected source(s) and
re-derives them — no re-scraping involved.

Examples:
    python -m app.ingestion.reprocess                      # rebuild all sources
    python -m app.ingestion.reprocess --source linkedin_profile
    python -m app.ingestion.reprocess --dry-run            # preview, write nothing
    python -m app.ingestion.reprocess --document-id <uuid> # one document (debug)
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from .. import db, ingestion
from ..config import settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="reprocess", description=__doc__)
    parser.add_argument(
        "--source",
        choices=["all", *ingestion.kinds()],
        default="all",
        help="which source kind to rebuild (default: all). Scopes BOTH the wipe and the rebuild.",
    )
    parser.add_argument("--document-id", help="reprocess a single source document by id (ignores --source)")
    parser.add_argument("--user-id", help="scope to a user id (default: local dev user)")
    parser.add_argument("--no-wipe", action="store_true", help="skip the delete; rely on content_hash dedupe")
    parser.add_argument("--dry-run", action="store_true", help="report what would happen; write nothing")
    parser.add_argument("--limit", type=int, help="cap the number of documents processed")
    parser.add_argument("-v", "--verbose", action="store_true", help="print per-document detail")
    return parser.parse_args()


async def _fetch_documents(
    user_id: str | None,
    kinds: list[str],
    document_id: str | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    if document_id:
        row = await db.fetch_one("SELECT * FROM source_documents WHERE id = %s", (document_id,))
        return [row] if row else []

    return await db.fetch_all(
        """
        SELECT * FROM source_documents
        WHERE kind = ANY(%s)
          AND (%s::uuid IS NULL OR user_id = %s)
        ORDER BY captured_at
        LIMIT %s
        """,
        (kinds, user_id, user_id, limit),
    )


async def _wipe(conn, user_id: str | None, kinds: list[str], source_all: bool, document_id: str | None) -> int:
    """Delete the memories derived from the in-scope source documents (never touches
    conversation/message-derived memories). user_id None => across all users."""
    if document_id:
        sql = "DELETE FROM memory_items WHERE source_document_id = %s"
        params: list[Any] = [document_id]
    elif source_all:
        sql = "DELETE FROM memory_items WHERE source_document_id IS NOT NULL"
        params = []
    else:
        sql = (
            "DELETE FROM memory_items WHERE source_document_id IN "
            "(SELECT id FROM source_documents WHERE kind = ANY(%s))"
        )
        params = [kinds]

    if user_id is not None and not document_id:
        sql += " AND user_id = %s"
        params.append(user_id)

    async with conn.transaction():
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            return cur.rowcount


async def main() -> None:
    args = _parse_args()
    source_all = args.source == "all"
    target_kinds = ingestion.kinds() if source_all else [args.source]

    async with db.open_database(settings.database_url):
        user_id = args.user_id  # None => all users

        documents = await _fetch_documents(user_id, target_kinds, args.document_id, args.limit)
        scope = f"source={args.source}, user={user_id or 'all'}"
        print(f"{len(documents)} document(s) in scope ({scope}).")

        async for conn in db.connection():
            if not args.no_wipe and not args.dry_run:
                deleted = await _wipe(conn, user_id, target_kinds, source_all, args.document_id)
                print(f"Wiped {deleted} derived memory_items.")

            total_memories = 0
            skipped = 0
            for document in documents:
                ingestor = ingestion.get_by_kind(document["kind"])
                if ingestor is None:
                    skipped += 1
                    print(f"  skip {document['id']}: no ingestor for kind {document['kind']!r}")
                    continue

                if args.dry_run:
                    drafts = ingestor.chunk(document)
                    print(f"  {document['id']} [{document['kind']}] -> {len(drafts)} memory draft(s)")
                    continue

                ids = await ingestor.atomize(conn, document)
                total_memories += len(ids)
                if args.verbose:
                    print(f"  {document['id']} [{document['kind']}] -> {len(ids)} memory_items")

            verb = "would create" if args.dry_run else "created"
            tail = f", {skipped} skipped" if skipped else ""
            print(f"Done: {verb} {total_memories} memory_items across {len(documents)} document(s){tail}.")


if __name__ == "__main__":
    asyncio.run(main())
