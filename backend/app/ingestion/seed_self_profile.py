"""Seed the user's self-profile into source_documents + memory_items.

The self-profile is hand-authored (not scrapable) and private, so the curated
markdown lives OUTSIDE the repo at `captures/self_profile.md` (gitignored). This
script reads that file, writes it verbatim into `source_documents`, and the
SelfProfileIngestor atomizes it into embedded `memory_items` (person_id NULL,
"facts about the sender").

Idempotent: content_hash dedupes the document and each memory, so re-running after
an edit only adds what changed (pair with
`python -m app.ingestion.reprocess --source self_profile` to fully rebuild).

Examples:
    python -m app.ingestion.seed_self_profile                 # ingest + atomize
    python -m app.ingestion.seed_self_profile --dry-run       # show drafts, write nothing
    python -m app.ingestion.seed_self_profile --file path/to/profile.md
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .. import db
from ..config import settings
from ..identity.users import get_or_create_dev_user_id, get_or_create_user_id_by_name
from . import get_by_kind
from .base import content_hash

# Default owner: the canonical local-dev account — the same user that owns the
# eval corpus + ingested recipient profiles — so the self-facts (person_id NULL)
# retrieve alongside a recipient's person-scoped facts. Decoupled from any human
# sender name; override with --user-name / --user-id only for ad-hoc seeding.

# Private, gitignored. Repo root is four parents up from this module.
DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[3] / "captures" / "self_profile.md"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="seed_self_profile", description=__doc__)
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_PROFILE_PATH,
        help=f"self-profile markdown to ingest (default: {DEFAULT_PROFILE_PATH})",
    )
    parser.add_argument("--user-name", default=None, help="own the self-profile by name (default: local-dev user)")
    parser.add_argument("--user-id", help="own the self-profile by user id (overrides --user-name)")
    parser.add_argument("--no-atomize", action="store_true", help="ingest the document only; skip memory build")
    parser.add_argument("--dry-run", action="store_true", help="show the memory drafts; write nothing")
    parser.add_argument("-v", "--verbose", action="store_true", help="print each memory draft")
    return parser.parse_args()


def _read_profile(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(
            f"Self-profile file not found: {path}\n"
            "Author it (gitignored) before seeding, e.g. cp it into captures/self_profile.md."
        )
    return path.read_text(encoding="utf-8")


async def _resolve_user_id(args: argparse.Namespace) -> str:
    if args.user_id:
        return args.user_id
    if args.user_name:
        return await get_or_create_user_id_by_name(args.user_name)
    return await get_or_create_dev_user_id()


async def main() -> None:
    args = _parse_args()
    markdown = _read_profile(args.file)
    ingestor = get_by_kind("self_profile")
    assert ingestor is not None  # registered in ingestion.__init__

    if args.dry_run:
        drafts = ingestor.chunk({"content": {"markdown": markdown}})
        print(f"[dry-run] {args.file}: {len(drafts)} memory draft(s):")
        for draft in drafts:
            print(f"  [{draft.memory_type}] {draft.content}")
        return

    async with db.open_database(settings.database_url):
        user_id = await _resolve_user_id(args)
        parsed = ingestor.parse(markdown, None)
        document_hash = content_hash(parsed.content)

        async for conn in db.connection():
            async with conn.transaction():
                result = await ingestor.ingest(conn, user_id, result=markdown, source_url=None)
            print(f"source_document: {result.status} (user={user_id})")

            if args.no_atomize:
                return

            document = await db.fetch_one(
                "SELECT * FROM source_documents WHERE user_id = %s AND content_hash = %s",
                (user_id, document_hash),
            )
            if document is None:
                raise RuntimeError("Self-profile document missing after ingest.")

            memory_ids = await ingestor.atomize(conn, document)
            print(f"memory_items: {len(memory_ids)} new (duplicates skipped)")
            if args.verbose:
                for draft in ingestor.chunk(document):
                    print(f"  [{draft.memory_type}] {draft.content}")
            return


if __name__ == "__main__":
    asyncio.run(main())
