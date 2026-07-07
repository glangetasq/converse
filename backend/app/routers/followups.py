from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.types.json import Jsonb

from .. import db
from ..config import settings
from ..llm import GenConfig, ModelError, get_client
from ..llm.embeddings import get_embedder
from ..loggers import api_logger
from ..prompting import LiveContext, LivePrompt, build_live_prompt
from ..utils import cosine_similarity
from ..web.dependencies import get_current_user
from ..web.models import FollowupFeedbackRequest, FollowupGenerateRequest, FollowupIngestRequest, LoginRequest
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
    cfg = GenConfig()

    try:
        completion = await client.generate(built.prompt, model, cfg)
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
            Jsonb(list(built.fact_ids)),
            model,
            completion.text,
            # everything needed to reproduce the suggestion later, alongside the
            # columns: model_name, generated_text, user_prompt, retrieved_memory_ids
            Jsonb(
                {
                    "promptSpec": dict(built.spec),
                    "promptVersion": built.version,
                    "genConfig": cfg.spec(),
                    "senderName": context.sender_name,
                    "recipientName": context.recipient_name,
                    "thread": list(context.thread),
                    "evidence": built.evidence,
                    "ragError": built.rag_error,
                    "sourceUrl": payload.source_url,
                    "source": payload.source,
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


async def original_final_similarity(original: str, final: str) -> float:
    embeddings = await get_embedder().embed([original, final])
    return cosine_similarity(embeddings[0], embeddings[1])


@router.post("/{generation_id}/ingest")
async def ingest_followup(
    generation_id: str,
    payload: FollowupIngestRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Record the user-approved final draft on its generation row: final text,
    accepted/edited flag, and cosine similarity between original and final."""
    generation = await db.fetch_one(
        "SELECT * FROM followup_generations WHERE user_id = %s AND id = %s",
        (user["id"], generation_id),
    )
    if generation is None:
        raise HTTPException(status_code=404, detail="Follow-up generation not found")

    original = generation["generated_text"]
    final = payload.final_draft.strip()
    user_feedback = "accepted" if final == original.strip() else "edited"

    similarity: float | None = None
    similarity_error: str | None = None
    try:
        similarity = await original_final_similarity(original, final)
    except Exception as error:  # noqa: BLE001 — an ingest without similarity beats no ingest
        similarity_error = str(error)
        api_logger.warning("Similarity computation failed during ingest: %s", similarity_error)

    metadata = dict(generation["metadata"] or {})
    metadata.update(
        {
            "similarityError": similarity_error,
            "ingestedAt": datetime.now(timezone.utc).isoformat(),
        }
    )

    updated = await db.fetch_one(
        """
        UPDATE followup_generations
        SET final_sent_text = %s,
            user_feedback = %s,
            original_final_similarity = %s,
            metadata = %s
        WHERE user_id = %s AND id = %s
        RETURNING *
        """,
        (final, user_feedback, similarity, Jsonb(metadata), user["id"], generation_id),
    )

    api_logger.info(
        "Ingested follow-up %s (%s, similarity=%s)",
        generation_id,
        user_feedback,
        f"{similarity:.4f}" if similarity is not None else "n/a",
    )

    return {
        "generationId": str(updated["id"]),
        "userFeedback": user_feedback,
        "originalFinalSimilarity": similarity,
        "similarityError": similarity_error,
        "ingestedAt": metadata["ingestedAt"],
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
