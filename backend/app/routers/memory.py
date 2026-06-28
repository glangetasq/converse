from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from .. import db
from ..dependencies import get_current_user
from ..models import MemoryGenerationRequest, MemorySearchRequest
from ..serialization import to_api


router = APIRouter()


@router.post("/generate")
async def generate_memory(
    payload: MemoryGenerationRequest,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "status": "placeholder",
        "conversationId": str(payload.conversation_id),
        "personId": str(payload.person_id) if payload.person_id else None,
        "todo": "Implement message chunking, structured memory extraction, deduping, embeddings, and persistence.",
    }


@router.post("/search")
async def search_memory(
    payload: MemorySearchRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    conditions = ["user_id = %s", "content ILIKE %s"]
    params: list[Any] = [user["id"], f"%{payload.query}%"]

    if payload.person_id:
        conditions.append("person_id = %s")
        params.append(str(payload.person_id))

    if payload.conversation_id:
        conditions.append("conversation_id = %s")
        params.append(str(payload.conversation_id))

    params.append(payload.limit)
    rows = await db.fetch_all(
        f"""
        SELECT *
        FROM memory_items
        WHERE {" AND ".join(conditions)}
        ORDER BY created_at DESC
        LIMIT %s
        """,
        params,
    )

    return {
        "status": "placeholder",
        "todo": "Replace ILIKE with pgvector similarity search and hybrid reranking.",
        "results": to_api(rows),
    }

