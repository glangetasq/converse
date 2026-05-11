from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class PersonInput(ApiModel):
    full_name: str | None = Field(default=None, alias="fullName")
    email: EmailStr | None = None
    linkedin_url: HttpUrl | None = Field(default=None, alias="linkedinUrl")
    company: str | None = None
    role_title: str | None = Field(default=None, alias="roleTitle")


class MessageInput(ApiModel):
    source_message_id: str | None = Field(default=None, alias="sourceMessageId")
    sender_name: str | None = Field(default=None, alias="senderName")
    sender_type: Literal["user", "contact", "unknown"] = Field(alias="senderType")
    body: str
    sent_at: str | None = Field(default=None, alias="sentAt")
    message_order: int = Field(alias="messageOrder", ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImportConversationRequest(ApiModel):
    source: Literal["linkedin", "gmail"]
    external_thread_id: str | None = Field(default=None, alias="externalThreadId")
    raw_url: HttpUrl | None = Field(default=None, alias="rawUrl")
    title: str | None = None
    person: PersonInput | None = None
    messages: list[MessageInput] = Field(min_length=1)


class FollowupGenerationRequest(ApiModel):
    person_id: UUID | None = Field(default=None, alias="personId")
    conversation_id: UUID | None = Field(default=None, alias="conversationId")
    user_prompt: str | None = Field(default=None, alias="userPrompt")
    tone: str | None = None
    target_length: str | None = Field(default=None, alias="targetLength")


class FollowupFeedbackRequest(ApiModel):
    user_feedback: Literal["accepted", "edited", "rejected"] = Field(alias="userFeedback")
    final_sent_text: str | None = Field(default=None, alias="finalSentText")


class MemoryGenerationRequest(ApiModel):
    conversation_id: UUID = Field(alias="conversationId")
    person_id: UUID | None = Field(default=None, alias="personId")


class MemorySearchRequest(ApiModel):
    person_id: UUID | None = Field(default=None, alias="personId")
    conversation_id: UUID | None = Field(default=None, alias="conversationId")
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)

