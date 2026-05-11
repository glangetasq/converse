from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from .. import db
from ..dependencies import get_current_user
from ..models import ImportConversationRequest, MessageInput, PersonInput
from ..serialization import to_api


router = APIRouter()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _person_values(person: PersonInput, user_id: str, source: str) -> tuple[Any, ...]:
    full_name = person.full_name.strip() if person.full_name else None
    return (
        user_id,
        full_name,
        full_name.lower() if full_name else None,
        str(person.linkedin_url) if person.linkedin_url else None,
        str(person.email) if person.email else None,
        person.company,
        person.role_title,
        source,
    )


async def _find_or_create_person(
    conn: AsyncConnection,
    user_id: str,
    source: str,
    person: PersonInput | None,
) -> dict[str, Any] | None:
    if person is None:
        return None

    email = str(person.email) if person.email else None
    linkedin_url = str(person.linkedin_url) if person.linkedin_url else None

    if email or linkedin_url:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM persons
                WHERE user_id = %s
                  AND (
                    (%s IS NOT NULL AND email = %s)
                    OR (%s IS NOT NULL AND linkedin_url = %s)
                  )
                LIMIT 1
                """,
                (user_id, email, email, linkedin_url, linkedin_url),
            )
            existing = await cur.fetchone()
            if existing:
                return existing

    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO persons (
              user_id, full_name, normalized_name, linkedin_url, email,
              company, role_title, source_first_seen
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            _person_values(person, user_id, source),
        )
        return await cur.fetchone()


def _conversation_dates(messages: list[MessageInput]) -> tuple[datetime | None, datetime | None]:
    dates = [_parse_datetime(message.sent_at) for message in messages]
    present_dates = [date for date in dates if date is not None]

    if not present_dates:
        return None, None

    return min(present_dates), max(present_dates)


async def _find_existing_conversation(
    conn: AsyncConnection,
    user_id: str,
    source: str,
    external_thread_id: str | None,
) -> dict[str, Any] | None:
    if not external_thread_id:
        return None

    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT *
            FROM conversations
            WHERE user_id = %s AND source = %s AND external_thread_id = %s
            LIMIT 1
            """,
            (user_id, source, external_thread_id),
        )
        return await cur.fetchone()


async def _upsert_conversation(
    conn: AsyncConnection,
    user_id: str,
    payload: ImportConversationRequest,
    person: dict[str, Any] | None,
) -> dict[str, Any]:
    started_at, last_message_at = _conversation_dates(payload.messages)
    raw_url = str(payload.raw_url) if payload.raw_url else None
    existing = await _find_existing_conversation(conn, user_id, payload.source, payload.external_thread_id)

    async with conn.cursor() as cur:
        if existing:
            await cur.execute(
                """
                UPDATE conversations
                SET person_id = COALESCE(%s, person_id),
                    title = COALESCE(%s, title),
                    raw_url = COALESCE(%s, raw_url),
                    started_at = COALESCE(started_at, %s),
                    last_message_at = COALESCE(%s, last_message_at),
                    updated_at = now()
                WHERE id = %s
                RETURNING *
                """,
                (
                    person["id"] if person else None,
                    payload.title,
                    raw_url,
                    started_at,
                    last_message_at,
                    existing["id"],
                ),
            )
            updated = await cur.fetchone()
            if updated is None:
                raise RuntimeError("Conversation update did not return a row.")
            return updated

        await cur.execute(
            """
            INSERT INTO conversations (
              user_id, person_id, source, external_thread_id, title,
              raw_url, started_at, last_message_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                user_id,
                person["id"] if person else None,
                payload.source,
                payload.external_thread_id,
                payload.title,
                raw_url,
                started_at,
                last_message_at,
            ),
        )
        created = await cur.fetchone()
        if created is None:
            raise RuntimeError("Conversation insert did not return a row.")
        return created


async def _existing_source_message_ids(
    conn: AsyncConnection,
    conversation_id: str,
    messages: list[MessageInput],
) -> set[str]:
    source_ids = [message.source_message_id for message in messages if message.source_message_id]
    if not source_ids:
        return set()

    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT source_message_id
            FROM messages
            WHERE conversation_id = %s AND source_message_id = ANY(%s)
            """,
            (conversation_id, source_ids),
        )
        rows = await cur.fetchall()
        return {row["source_message_id"] for row in rows if row["source_message_id"]}


async def _insert_messages(
    conn: AsyncConnection,
    user_id: str,
    conversation_id: str,
    person_id: str | None,
    messages: list[MessageInput],
) -> list[dict[str, Any]]:
    existing_source_ids = await _existing_source_message_ids(conn, conversation_id, messages)
    inserted: list[dict[str, Any]] = []

    async with conn.cursor() as cur:
        for message in messages:
            if message.source_message_id and message.source_message_id in existing_source_ids:
                continue

            await cur.execute(
                """
                INSERT INTO messages (
                  conversation_id, user_id, person_id, source_message_id,
                  sender_name, sender_type, body, sent_at, message_order, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING *
                """,
                (
                    conversation_id,
                    user_id,
                    person_id,
                    message.source_message_id,
                    message.sender_name,
                    message.sender_type,
                    message.body,
                    _parse_datetime(message.sent_at),
                    message.message_order,
                    Jsonb(message.metadata),
                ),
            )
            row = await cur.fetchone()
            if row:
                inserted.append(row)

    return inserted


async def _conversation_with_messages(
    conn: AsyncConnection,
    user_id: str,
    conversation_id: str,
) -> dict[str, Any] | None:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM conversations WHERE user_id = %s AND id = %s LIMIT 1",
            (user_id, conversation_id),
        )
        conversation = await cur.fetchone()
        if conversation is None:
            return None

        await cur.execute(
            """
            SELECT *
            FROM messages
            WHERE conversation_id = %s
            ORDER BY message_order ASC, created_at ASC
            """,
            (conversation_id,),
        )
        messages = await cur.fetchall()

    return {"conversation": conversation, "messages": messages}


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_conversation(
    payload: ImportConversationRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    user_id = user["id"]

    async for conn in db.connection():
        async with conn.transaction():
            person = await _find_or_create_person(conn, user_id, payload.source, payload.person)
            conversation = await _upsert_conversation(conn, user_id, payload, person)
            inserted_messages = await _insert_messages(
                conn,
                user_id,
                str(conversation["id"]),
                str(person["id"]) if person else None,
                payload.messages,
            )
            stored = await _conversation_with_messages(conn, user_id, str(conversation["id"]))

    return to_api({
        "conversation": stored["conversation"] if stored else conversation,
        "messages": stored["messages"] if stored else inserted_messages,
        "importedMessageCount": len(inserted_messages),
        "person": person,
    })


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    async for conn in db.connection():
        result = await _conversation_with_messages(conn, user["id"], conversation_id)

    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return to_api(result)

