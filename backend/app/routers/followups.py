from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.types.json import Jsonb

from .. import db
from ..config import settings
from ..llm import GenConfig, ModelError, get_client
from ..loggers import api_logger
from ..prompting import LiveContext, LivePrompt, build_live_prompt
from ..web.dependencies import get_current_user
from ..web.models import FollowupFeedbackRequest, FollowupGenerateRequest, LoginRequest
from ..web.serialization import to_api
from .persons import get_or_create_person_id_by_name

router = APIRouter()

DEFAULT_SENDER_NAME = LoginRequest.model_fields["username"].default


async def build_request_context(user_id: str, payload: FollowupGenerateRequest) -> LiveContext:
    person_id = await get_or_create_person_id_by_name(user_id, payload.recipient_name, payload.source)
    thread = [
        {"sender_name": message.sender_name, "sent_time": message.sent_time, "body": message.body}
        for message in sorted(payload.messages, key=lambda message: message.message_order)
    ]
    return LiveContext(
        thread=thread,
        sender_name=payload.sender_name or DEFAULT_SENDER_NAME,
        recipient_name=payload.recipient_name,
        meta={"user_id": user_id, "person_id": person_id},
    )


def prompt_response(built: LivePrompt) -> dict[str, Any]:
    return {
        "prompt": built.prompt,
        "evidence": built.evidence,
        "promptVersion": built.version,
        "ragError": built.rag_error,
    }


@router.post("/preview")
async def preview_followup_prompt(
    payload: FollowupGenerateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Assemble the exact generation prompt (template + RAG facts + sender context)
    without calling a model or persisting anything."""
    context = await build_request_context(user["id"], payload)
    built = await build_live_prompt(context, payload.additional_context)
    return prompt_response(built)


@router.post("/generate")
async def generate_followup(
    payload: FollowupGenerateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    model = payload.model or settings.default_model
    try:
        client = get_client(model)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

    context = await build_request_context(user["id"], payload)
    built = await build_live_prompt(context, payload.additional_context)

    try:
        completion = await client.generate(built.prompt, model, GenConfig())
    except ModelError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error))

    generation = await db.fetch_one(
        """
        INSERT INTO followup_generations (
          user_id, person_id, user_prompt, retrieved_memory_ids,
          model_name, generated_text, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            user["id"],
            context.meta["person_id"],
            payload.additional_context,
            Jsonb([]),
            model,
            completion.text,
            Jsonb(
                {
                    "promptVersion": built.version,
                    "evidence": built.evidence,
                    "ragError": built.rag_error,
                    "sourceUrl": payload.source_url,
                    "threadLength": len(context.thread),
                    "usage": completion.usage,
                }
            ),
        ),
    )

    api_logger.info(
        "Generated follow-up %s (model=%s, thread=%d msgs, rag=%s)",
        generation["id"] if generation else "?",
        model,
        len(context.thread),
        "on" if built.evidence else "off",
    )

    return {
        "generationId": str(generation["id"]) if generation else None,
        "suggestion": completion.text,
        "model": model,
        **prompt_response(built),
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
