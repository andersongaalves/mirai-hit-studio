"""Explicit contracts for the authenticated AI Inbox."""

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated

from schemas.ai import Channel, ConversationMode, ConversationStatus, HandoffReason
from schemas.ai_briefing import BriefingAdminOutput


class InboxMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    direction: Literal["inbound", "outbound"]
    role: Literal["user", "assistant"]
    kind: Literal["message", "reply", "suggestion"]
    content: str
    created_at: datetime
    received_at: datetime | None = None
    delivery: Literal["draft", "pending", "sent"]


class InboxListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    channel: Channel
    status: ConversationStatus
    mode: ConversationMode
    assigned_user_id: int | None = None
    assigned_username: str | None = None
    cliente_id: int | None = None
    cliente_nome: str | None = None
    email_subject: str | None = None
    handoff_reason: HandoffReason | None = None
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class InboxPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[InboxListItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    pages: int = Field(ge=0)


class InboxDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    channel: Channel
    status: ConversationStatus
    mode: ConversationMode
    assigned_user_id: int | None = None
    assigned_username: str | None = None
    cliente_id: int | None = None
    cliente_nome: str | None = None
    cliente_email: str | None = None
    sender_reference: str | None = None
    email_subject: str | None = None
    handoff_reason: HandoffReason | None = None
    version: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    messages: list[InboxMessage]
    has_more_messages: bool = False
    next_before: UUID | None = None
    briefing: BriefingAdminOutput | None = None


class InboxModeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: ConversationMode


class InboxMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
    suggestion_id: UUID | None = None
    idempotency_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=64)] = Field(
        default_factory=lambda: str(uuid4()), pattern=r"^[A-Za-z0-9._-]{8,64}$"
    )


class InboxSuggestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: UUID | None = None


class InboxSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    conversation_id: UUID
    target_message_id: UUID
    text: str
    created_at: datetime


class InboxMutationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation: InboxDetail


class InboxMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: InboxMessage
    delivery: Literal["sent", "already_sent"]


class InboxSuggestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    suggestion: InboxSuggestion
