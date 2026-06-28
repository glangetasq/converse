from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


KEY_MAP = {
    "created_at": "createdAt",
    "updated_at": "updatedAt",
    "display_name": "displayName",
    "user_id": "userId",
    "full_name": "fullName",
    "normalized_name": "normalizedName",
    "linkedin_url": "linkedinUrl",
    "source_first_seen": "sourceFirstSeen",
    "person_id": "personId",
    "external_thread_id": "externalThreadId",
    "raw_url": "rawUrl",
    "started_at": "startedAt",
    "last_message_at": "lastMessageAt",
    "conversation_id": "conversationId",
    "message_id": "messageId",
    "source_message_id": "sourceMessageId",
    "sender_name": "senderName",
    "sender_type": "senderType",
    "sent_at": "sentAt",
    "message_order": "messageOrder",
    "memory_type": "memoryType",
    "content_hash": "contentHash",
    "user_prompt": "userPrompt",
    "target_length": "targetLength",
    "retrieved_memory_ids": "retrievedMemoryIds",
    "model_name": "modelName",
    "generated_text": "generatedText",
    "user_feedback": "userFeedback",
    "final_sent_text": "finalSentText",
}


def to_api(value: Any) -> Any:
    if isinstance(value, list):
        return [to_api(item) for item in value]

    if isinstance(value, dict):
        return {KEY_MAP.get(key, key): to_api(item) for key, item in value.items()}

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, Decimal):
        return float(value)

    return value

