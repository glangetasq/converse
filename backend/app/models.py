from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class PersonInput(ApiModel):
    full_name: str | None = Field(default=None, alias="fullName")
    email: EmailStr | None = None
    linkedin_url: HttpUrl | None = Field(default=None, alias="linkedinUrl")


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


class LoginRequest(ApiModel):
    username: str = Field(default="Quentin Glangetas", min_length=1, max_length=200)


class EvalExampleMessage(ApiModel):
    message_order: int
    sender_name: str
    body: str
    rating: int = Field(ge=1, le=5)
    category: str | None = None
    sent_time: datetime | None = Field(alias="sentTime")


class EvalExampleCreateRequest(ApiModel):  # completely wrong, it should give a list of messages mostly
    saved_at: datetime = Field(default_factory=datetime.now)
    source: str
    user_name: str = Field(min_length=1)
    recipient_name: str | None = Field(default=None)
    messages: list[EvalExampleMessage] = Field(min_length=1)


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


class ParseDumpRequest(ApiModel):
    # `result` is the parsed profile JSON; kept as Any so any parser shape passes through verbatim.
    result: Any
    # `parser_id` selects the ingester (e.g. 'linkedin-profile'); `label` is just the filename hint.
    parser_id: str | None = Field(default=None, alias="parserId")
    label: str | None = None
    source_url: str | None = Field(default=None, alias="sourceUrl")
