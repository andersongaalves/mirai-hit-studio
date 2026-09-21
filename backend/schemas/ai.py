"""Channel-neutral boundaries. Provider and channel payloads never enter ORM objects."""

from datetime import datetime
from enum import Enum
import json
from typing import Annotated, Any, Literal, Protocol
from uuid import UUID

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator,
    model_validator,
)


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
ToolName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{2,63}$")]


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
        "processing_conflict", "retry_exhausted", "tool_not_allowed",
        "tool_invalid_arguments", "tool_not_authorized", "tool_temporarily_unavailable",
        "tool_loop_limit", "tool_call_limit", "tool_invalid_result",
    ] | None = None
    retryable: bool = False


class HistoryEntry(Contract):
    role: Literal["user", "assistant"]
    text: Text


class ProviderToolDefinition(Contract):
    name: ToolName
    description: str = Field(min_length=1, max_length=500)
    input_schema: dict[str, Any]


class ToolCall(Contract):
    id: Reference
    name: ToolName
    arguments: dict[str, Any] = Field(default_factory=dict)

    @field_validator("arguments")
    @classmethod
    def validate_arguments_size(cls, value):
        if len(value) > 16 or len(json.dumps(value, default=str)) > 8000:
            raise ValueError("Tool arguments exceed limits")
        return value


ToolErrorCode = Literal[
    "not_found", "not_authorized", "invalid_input", "temporarily_unavailable",
    "conflict", "not_allowed", "invalid_result",
]


class ProviderToolResult(Contract):
    call_id: Reference
    name: ToolName
    success: bool
    data: dict[str, Any] | None = None
    error_code: ToolErrorCode | None = None

    @model_validator(mode="after")
    def validate_result(self):
        if self.success == (self.error_code is not None):
            raise ValueError("Tool result must contain either data or an error")
        if not self.success and self.data is not None:
            raise ValueError("Failed tool result cannot contain data")
        return self


class ProviderInput(Contract):
    system: str = Field(min_length=1, max_length=2000)
    message: Text
    history: tuple[HistoryEntry, ...] = Field(default=(), max_length=20)
    context: tuple[Text, ...] = Field(default=(), max_length=8)
    tools: tuple[ProviderToolDefinition, ...] = Field(default=(), max_length=12)
    tool_results: tuple[ProviderToolResult, ...] = Field(default=(), max_length=4)


class ProviderResponse(Contract):
    text: Text | None = None
    handoff_reason: HandoffReason | None = None
    tool_calls: tuple[ToolCall, ...] = Field(default=(), max_length=3)
    model: str | None = Field(default=None, max_length=100)
    usage_tokens: int | None = Field(default=None, ge=0)
    finish_reason: Literal["stop", "length"] = "stop"

    @model_validator(mode="after")
    def validate_action(self):
        actions = (self.text is not None, self.handoff_reason is not None, bool(self.tool_calls))
        if sum(actions) != 1:
            raise ValueError("Exactly one response, handoff or tool request is required")
        return self


class ChannelAdapter(Protocol):
    def normalize(self, payload: object, received_at: datetime) -> InboundMessage: ...

    def send(self, message: OutboundMessage) -> str:
        """Use message.id for delivery deduplication; never auto-send suggestions."""
        ...
