from __future__ import annotations

from typing import Any

from dataclasses import dataclass
from datetime import datetime
from fastapi import APIRouter, status
from psycopg.types.json import Jsonb


from ..loggers import eval_logger
from ..models import EvalExampleCreateRequest
from .persons import get_or_create_person_id_by_name
from ..users import get_or_create_user_id_by_name, normalize_username
from .. import db

router = APIRouter()


@dataclass
class EvalExampleSqlRow:
    user_id: str
    recipient_id: str | None
    eval_thread_id: int
    source: str
    past_context: list | dict
    ground_truth_reply: str
    ground_truth_time: datetime
    quality_rating: int
    quality_rating_time: datetime
    recipient_replied: bool = False
    recipient_quality_rating: int | None = None


async def get_new_eval_thread_id() -> int:
    sql = "SELECT MAX(eval_thread_id) AS max_thread_id FROM eval_examples"
    max_thread_id = await db.fetch_one(sql)
    max_thread_id = max_thread_id.get("max_thread_id") or 0
    return max_thread_id + 1


def normalize_sender_name(value: str | None) -> str:
    return normalize_username(value or "").casefold()


def is_user_sender(user_name: str, sender_name: str | None) -> bool:
    # TODO: Replace name matching with an explicit sender identity from the parser payload.
    return normalize_sender_name(user_name) == normalize_sender_name(sender_name)


async def generate_examples(payload: EvalExampleCreateRequest) -> list[EvalExampleSqlRow]:
    user_id = await get_or_create_user_id_by_name(payload.user_name)
    recipient_id = (
        await get_or_create_person_id_by_name(user_id, payload.recipient_name, payload.source)
        if payload.recipient_name
        else None
    )
    new_thread_id = await get_new_eval_thread_id()
    messages = sorted(payload.messages, key=lambda msg: msg.message_order)

    past_context = []
    examples = []

    for msg in messages:
        current_context = {
            "sender_name": msg.sender_name,
            "sent_time": msg.sent_time.isoformat() if msg.sent_time else None,
            "body": msg.body,
        }

        if is_user_sender(payload.user_name, msg.sender_name):
            example = EvalExampleSqlRow(
                eval_thread_id=new_thread_id,
                user_id=user_id,
                recipient_id=recipient_id,
                source=payload.source,  # linkedin + intro = diff source
                past_context=list(past_context),  # deepcopy
                ground_truth_reply=msg.body,
                ground_truth_time=msg.sent_time,
                quality_rating=msg.rating,
                quality_rating_time=payload.saved_at,
                recipient_replied=False,
                recipient_quality_rating=None,
            )
            examples.append(example)
        else:
            # adjust past examples with new information
            for past_example in examples[::-1]:
                if past_example.recipient_replied or past_example.recipient_quality_rating is not None:
                    break
                past_example.recipient_replied = True
                past_example.recipient_quality_rating = msg.rating

        past_context.append(current_context)

    return examples


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def save_eval_example(payload: EvalExampleCreateRequest) -> dict[str, Any]:

    eval_logger.info(f"Received payload to save eval examples: {len(payload.messages) = }")

    examples = await generate_examples(payload)

    for example in examples:
        generation = await db.fetch_one(
            """
            INSERT INTO eval_examples (
                eval_thread_id,
                user_id,
                recipient_id,
                source,
                past_context,
                ground_truth_reply,
                ground_truth_time,
                quality_rating,
                quality_rating_time,
                recipient_replied,
                recipient_quality_rating
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                example.eval_thread_id,
                example.user_id,
                example.recipient_id,
                example.source,
                Jsonb(example.past_context),
                example.ground_truth_reply,
                example.ground_truth_time,
                example.quality_rating,
                example.quality_rating_time,
                example.recipient_replied,
                example.recipient_quality_rating,
            ),
        )

    eval_logger.info(f"Saved eval example: {len(payload.messages) = } | {len(examples) = }")

    return {"status": "saved"}
