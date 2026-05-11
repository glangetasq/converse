from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from .. import db
from ..dependencies import get_current_user
from ..serialization import to_api


router = APIRouter()


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
        ORDER BY importance_score DESC, created_at DESC
        """,
        (user["id"], person_id),
    )

    return {"memoryItems": to_api(rows)}

