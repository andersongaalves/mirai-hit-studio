from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None
    actor_username: str | None
    action: str
    entity_type: str
    entity_id: str | None
    metadata: dict[str, str | int | float | bool | None]
    request_id: str | None
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    pages: int = Field(ge=0)
