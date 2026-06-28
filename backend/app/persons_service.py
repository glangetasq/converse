"""Shared person resolution.

Single source of truth for "find an existing person by strong identifiers
(linkedin_url / email) or create them". Used by conversation import and by
ingestion so the dedupe logic lives in exactly one place.
"""

from __future__ import annotations

from typing import Any

from psycopg import AsyncConnection


async def find_or_create_person(
    conn: AsyncConnection,
    user_id: str,
    *,
    source: str,
    full_name: str | None = None,
    linkedin_url: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    """Resolve a person by linkedin_url / email, else insert. Returns the person row."""
    full_name = full_name.strip() if full_name else None
    linkedin_url = linkedin_url or None
    email = email or None

    if linkedin_url or email:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM persons
                WHERE user_id = %s
                  AND (
                    (%s::text IS NOT NULL AND linkedin_url = %s)
                    OR (%s::text IS NOT NULL AND email = %s)
                  )
                LIMIT 1
                """,
                (user_id, linkedin_url, linkedin_url, email, email),
            )
            existing = await cur.fetchone()
            if existing:
                return existing

    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO persons (
              user_id, full_name, normalized_name, linkedin_url, email, source_first_seen
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (user_id, full_name, full_name.casefold() if full_name else None, linkedin_url, email, source),
        )
        created = await cur.fetchone()

    if created is None:
        raise RuntimeError("Unable to resolve person.")

    return created
