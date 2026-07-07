from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.types.json import Jsonb

from .. import db
from ..config import settings
from ..evaluation.linkedin import LivePrompt, generate_live, preview_live
from ..llm.embeddings import get_embedder
from ..loggers import api_logger
from ..utils import cosine_similarity
from ..web.dependencies import get_current_user
from ..web.models import FollowupFeedbackRequest, FollowupGenerateRequest, FollowupIngestRequest, LoginRequest
from ..web.serialization import to_api
from .persons import get_or_create_person_id_by_name

router = APIRouter()

DEFAULT_SENDER_NAME = LoginRequest.model_fields["username"].default


async def build_case_kwargs(user_id: str, payload: FollowupGenerateRequest) -> dict[str, Any]:
    """Resolve recipient + thread into the live-generation helpers' kwargs. Person
    resolution is app logic, so it stays here rather than in the factory."""
    person_id = await get_or_create_person_id_by_name(user_id, payload.recipient_name, payload.source)
    thread = [
        {"sender_name": message.sender_name, "sent_time": message.sent_time, "body": message.body}
        for message in sorted(payload.messages, key=lambda message: message.message_order)
    ]
    return {
        "thread": thread,
        "sender_name": payload.sender_name or DEFAULT_SENDER_NAME,
        "recipient_name": payload.recipient_name,
        "user_id": user_id,
        "person_id": person_id,
        "additional_context": payload.additional_context,
    }


def prompt_response(prompt: LivePrompt) -> dict[str, Any]:
    return {
        "prompt": prompt.prompt,
        "evidence": prompt.evidence,
        "promptVersion": prompt.version,
        "ragError": prompt.rag_error,
    }


@router.post("/preview")
async def preview_followup_prompt(
    payload: FollowupGenerateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """The exact generation prompt, no model call and nothing persisted."""
    model = payload.model or settings.default_model
    case_kwargs = await build_case_kwargs(user["id"], payload)
    try:
        prompt = await preview_live(model, **case_kwargs)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    return prompt_response(prompt)


@router.post("/generate")
async def generate_followup(
    payload: FollowupGenerateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    model = payload.model or settings.default_model
    case_kwargs = await build_case_kwargs(user["id"], payload)

    try:
        generation = await generate_live(model, **case_kwargs)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

    if generation.error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=generation.error)

    prompt = generation.prompt
    row = await db.fetch_one(
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
            case_kwargs["person_id"],
            payload.additional_context,
            Jsonb(list(prompt.fact_ids)),
            model,
            generation.text,
            # reproduction trace, on top of the dedicated columns above
            Jsonb(
                {
                    "promptSpec": prompt.spec,
                    "promptVersion": prompt.version,
                    "genConfig": prompt.spec.get("gen"),
                    "senderName": case_kwargs["sender_name"],
                    "recipientName": case_kwargs["recipient_name"],
                    "thread": case_kwargs["thread"],
                    "evidence": prompt.evidence,
                    "ragError": prompt.rag_error,
                    "sourceUrl": payload.source_url,
                    "source": payload.source,
                    "usage": generation.usage,
                }
            ),
        ),
    )

    api_logger.info(
        "Generated follow-up %s (model=%s, thread=%d msgs, rag=%s)",
        row["id"] if row else "?",
        model,
        len(case_kwargs["thread"]),
        "on" if prompt.evidence else "off",
    )

    return {
        "generationId": str(row["id"]) if row else None,
        "suggestion": generation.text,
        "model": model,
        **prompt_response(prompt),
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
