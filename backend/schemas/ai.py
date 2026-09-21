"""Channel-neutral boundaries. Provider and channel payloads never enter ORM objects."""

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator


class ConversationStatus(str, Enum):
    OPEN = "open"
    WAITING_HUMAN = "waiting_human"
    CLOSED = "closed"


class ConversationMode(str, Enum):
    AUTONOMOUS = "autonomous"
    COPILOT = "copilot"
    HUMAN = "human"


class HandoffReason(str, Enum):
    NEGOTIATION = "negotiation"
    DISCOUNT = "discount"
    CUSTOM_PRICING = "custom_pricing"
    PAYMENT_ISSUE = "payment_issue"
    COMPLAINT = "complaint"
    LOW_CONFIDENCE = "low_confidence"
    TOOL_FAILURE = "tool_failure"
    PROVIDER_FAILURE = "provider_failure"
    MANUAL_REQUEST = "manual_request"
    OTHER = "other"


class DecisionAction(str, Enum):
    REPLY = "reply"
    SUGGESTION = "suggestion"
    HANDOFF = "handoff"
    NO_ACTION = "no_action"
    ERROR = "error"


Channel = Literal["site", "email"]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


class SafeMetadata(Contract):
    request_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._-]{8,64}$")


class ConversationCreate(Contract):
    channel: Channel
    mode: ConversationMode = ConversationMode.HUMAN
    cliente_id: int | None = Field(default=None, gt=0)
    assigned_user_id: int | None = Field(default=None, gt=0)
    anonymous_session_id: UUID | None = None
    external_thread_id: Reference | None = None
    sender_reference: Reference | None = None


class InboundMessage(Contract):
    channel: Channel
    external_message_id: Reference
    external_thread_id: Reference | None = None
    sender_reference: Reference | None = None
    text: Text
    received_at: AwareDatetime
    metadata: SafeMetadata = Field(default_factory=SafeMetadata)


class OutboundMessage(Contract):
    id: UUID
    conversation_id: UUID
    text: Text
    reply_to: Reference
    kind: Literal["reply", "suggestion"]
    metadata: SafeMetadata = Field(default_factory=SafeMetadata)


class ProcessingResult(Contract):
    conversation_id: UUID
    message_id: UUID
    action: DecisionAction
    outbound: OutboundMessage | None = None
    reason: HandoffReason | None = None
    error_code: Literal[
        "provider_unavailable", "provider_timeout", "provider_invalid_response",
        "processing_conflict", "retry_exhausted",
    ] | None = None
    retryable: bool = False


class HistoryEntry(Contract):
    role: Literal["user", "assistant"]
    text: Text


class ProviderInput(Contract):
    system: str = Field(min_length=1, max_length=2000)
    message: Text
    history: tuple[HistoryEntry, ...] = Field(default=(), max_length=20)
    context: tuple[Text, ...] = Field(default=(), max_length=8)


class ProviderResponse(Contract):
    text: Text | None = None
    handoff_reason: HandoffReason | None = None
    model: str | None = Field(default=None, max_length=100)
    usage_tokens: int | None = Field(default=None, ge=0)
    finish_reason: Literal["stop", "length"] = "stop"

    @model_validator(mode="after")
    def validate_action(self):
        if (self.text is None) == (self.handoff_reason is None):
            raise ValueError("Exactly one response or handoff is required")
        return self


class ChannelAdapter(Protocol):
    def normalize(self, payload: object, received_at: datetime) -> InboundMessage: ...

    def send(self, message: OutboundMessage) -> str:
        """Use message.id for delivery deduplication; never auto-send suggestions."""
        ...
