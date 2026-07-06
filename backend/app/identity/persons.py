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
    """Resolve a person by linkedin_url / email, then by name, else insert.

    Resolution order:
      1. strong identifiers (linkedin_url / email) — exact, cross-name-safe.
      2. normalized_name — reuses a person first seen without a strong identifier
         (e.g. an eval recipient created name-only), and BACKFILLS the linkedin_url
         / email we now have so the two paths converge on one row.
      3. insert a new person.
    Returns the person row.
    """
    full_name = full_name.strip() if full_name else None
    linkedin_url = linkedin_url or None
    email = email or None
    normalized_name = full_name.casefold() if full_name else None

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

    if normalized_name:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM persons
                WHERE user_id = %s AND normalized_name = %s
                LIMIT 1
                """,
                (user_id, normalized_name),
            )
            existing = await cur.fetchone()
        if existing:
            # Backfill strong identifiers onto an existing name-only row.
            if (linkedin_url and not existing.get("linkedin_url")) or (email and not existing.get("email")):
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE persons
                        SET linkedin_url = COALESCE(linkedin_url, %s),
                            email = COALESCE(email, %s),
                            updated_at = now()
                        WHERE id = %s
                        RETURNING *
                        """,
                        (linkedin_url, email, existing["id"]),
                    )
                    updated = await cur.fetchone()
                    if updated is not None:
                        return updated
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
