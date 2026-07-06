from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from .. import db
from ..web.dependencies import get_current_user
from ..web.serialization import to_api
from ..identity.users import normalize_username

router = APIRouter()


async def get_or_create_person_id_by_name(
    user_id: str,
    person_name: str,
    source: str,
) -> str:
    full_name = normalize_username(person_name)
    normalized_name = full_name.casefold()

    existing = await db.fetch_one(
        """
        SELECT id
        FROM persons
        WHERE user_id = %s AND normalized_name = %s
        LIMIT 1
        """,
        (user_id, normalized_name),
    )
    if existing:
        return str(existing["id"])

    created = await db.fetch_one(
        """
        INSERT INTO persons (
          user_id, full_name, normalized_name, source_first_seen
        )
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (user_id, full_name, normalized_name, source),
    )
    if created is None:
        raise RuntimeError("Unable to resolve person.")

    return str(created["id"])


async def get_person_id_to_name_dict() -> dict[str, str]:
    rows = await db.fetch_all(
        """
        SELECT id, full_name AS name
        FROM persons
        ORDER BY full_name, id
        """,
    )

    return {str(row["id"]): row["name"] or "" for row in rows}


@router.get("/{person_id}/memory")
async def list_person_memory(
    person_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    rows = await db.fetch_all(
        """
        SELECT *
        FROM memory_items
        WHERE user_id = %s AND person_id = %s
        ORDER BY created_at DESC
        """,
        (user["id"], person_id),
    )

    return {"memoryItems": to_api(rows)}
