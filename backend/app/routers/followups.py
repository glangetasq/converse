from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb

from .. import db
from ..dependencies import get_current_user
from ..models import FollowupFeedbackRequest, FollowupGenerationRequest
from ..serialization import to_api


router = APIRouter()


@router.post("/generate")
async def generate_followup(
    payload: FollowupGenerationRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    todo = "Implement memory retrieval, prompt assembly, provider client call, and persistence."
    generation = await db.fetch_one(
        """
        INSERT INTO followup_generations (
          user_id, person_id, conversation_id, user_prompt, tone,
          target_length, retrieved_memory_ids, model_name, generated_text, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            user["id"],
            str(payload.person_id) if payload.person_id else None,
            str(payload.conversation_id) if payload.conversation_id else None,
            payload.user_prompt,
            payload.tone,
            payload.target_length,
            Jsonb([]),
            None,
            "",
            Jsonb({"todo": todo}),
        ),
    )

    return {
        "status": "placeholder",
        "todo": todo,
        "generatedText": "",
        "generation": to_api(generation),
    }


@router.post("/{generation_id}/feedback")
async def save_feedback(
    generation_id: str,
    payload: FollowupFeedbackRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    generation = await db.fetch_one(
        """
        UPDATE followup_generations
        SET user_feedback = %s,
            final_sent_text = %s
        WHERE user_id = %s AND id = %s
        RETURNING *
        """,
        (payload.user_feedback, payload.final_sent_text, user["id"], generation_id),
    )

    if generation is None:
        raise HTTPException(status_code=404, detail="Follow-up generation not found")

    return to_api(generation)

