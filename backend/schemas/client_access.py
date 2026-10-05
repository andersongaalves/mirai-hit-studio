from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.usuario import validar_senha, validar_username

ClientAccessState = Literal[
    "sem_acesso",
    "convite_pendente",
    "convite_expirado",
    "convite_revogado",
    "conta_ativa",
    "conta_desativada",
    "conflito",
]


class ClientAccessStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposta_id: int
    cliente_id: int
    cliente_nome: str
    email: str | None
    proposta_status: str
    estado: ClientAccessState
    usuario_id: int | None = None
    last_sent_at: datetime | None = None
    expires_at: datetime | None = None
    send_count: int = 0


class ClientInviteToken(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=32, max_length=512)


class ClientInviteValidation(BaseModel):
    estado: Literal["valido", "expirado", "revogado", "utilizado"]


class ClientInviteActivation(ClientInviteToken):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("username")
    @classmethod
    def username_valido(cls, value: str) -> str:
        return validar_username(value)

    @field_validator("password")
    @classmethod
    def password_valido(cls, value: str) -> str:
        return validar_senha(value)


class ClientInviteActivationResult(BaseModel):
    activated: bool
    login_url: str
