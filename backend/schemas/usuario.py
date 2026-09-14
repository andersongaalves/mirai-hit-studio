from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


UsuarioRole = Literal["admin", "produtor"]


def validar_username(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("username_required")
    return value


def validar_senha(value: str) -> str:
    if len(value) < 8:
        raise ValueError("password_too_short")
    if len(value.encode("utf-8")) > 72:
        raise ValueError("password_exceeds_72_bytes")
    return value


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
        return validar_username(value)


class UsuarioCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=72)
    role: UsuarioRole = "produtor"

    @field_validator("username")
    @classmethod
    def username_valido(cls, value: str) -> str:
        return validar_username(value)

    @field_validator("password")
    @classmethod
    def password_valido(cls, value: str) -> str:
        return validar_senha(value)


class UsuarioUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = Field(default=None, min_length=1, max_length=50)
    role: UsuarioRole | None = None
    ativo: StrictBool | None = None

    @field_validator("username")
    @classmethod
    def username_valido(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("field_cannot_be_null")
        return validar_username(value)

    @field_validator("role", "ativo")
    @classmethod
    def campo_nao_nulo(cls, value):
        if value is None:
            raise ValueError("field_cannot_be_null")
        return value


class UsuarioPasswordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nova_senha: str = Field(min_length=8, max_length=72)

    @field_validator("nova_senha")
    @classmethod
    def password_valido(cls, value: str) -> str:
        return validar_senha(value)


class UsuarioResponse(BaseModel):

    id: int
    username: str
    role: str
    is_admin: bool
    ativo: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UsuarioResponse
