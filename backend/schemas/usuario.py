from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=72)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("password_exceeds_72_bytes")
        return value

    @field_validator("username")
    @classmethod
    def username_not_blank(cls, value):
        if not value.strip():
            raise ValueError("username_required")
        return value


class UsuarioResponse(BaseModel):

    id: int
    username: str
    role: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}
