"""Public site contracts deliberately exclude identity and core processing fields."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SiteMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message_id: UUID
    message: str = Field(min_length=1, max_length=4000)


class SiteSession(BaseModel):
    session_token: str
    expires_at: datetime


class SiteHistoryMessage(BaseModel):
    message_id: str | None = None
    role: Literal["user", "assistant"]
    sender: Literal["client", "ai", "human"] | None = None
    text: str
    created_at: datetime


class SiteHistory(BaseModel):
    status: Literal["open", "waiting_human", "closed"]
    awaiting_human: bool = False
    briefing_started: bool = False
    lead_created: bool = False
    messages: list[SiteHistoryMessage]


class SiteReply(BaseModel):
    status: Literal["open", "waiting_human", "closed"]
    action: Literal["reply", "handoff", "no_action", "error"]
    text: str | None = None
    retryable: bool = False
    briefing_started: bool = False
    lead_created: bool = False
