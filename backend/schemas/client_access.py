from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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


class ClientSignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=1, max_length=120)
    email: EmailStr = Field(max_length=150)
    telefone: str | None = Field(default=None, max_length=30)
    privacy_accepted: bool

    @field_validator("nome")
    @classmethod
    def nome_valido(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("nome_obrigatorio")
        return value

    @field_validator("telefone")
    @classmethod
    def telefone_valido(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("privacy_accepted")
    @classmethod
    def privacidade_obrigatoria(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("privacy_acceptance_required")
        return value


class ClientSignupResend(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=150)


class ClientSignupAccepted(BaseModel):
    accepted: bool = True
    message: str


class PasswordRecoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=150)


class PasswordRecoveryAccepted(BaseModel):
    accepted: bool = True
    message: str


class PasswordResetRequest(ClientInviteToken):
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_valido(cls, value: str) -> str:
        return validar_senha(value)


class PasswordResetResult(BaseModel):
    reset: bool
    login_url: str
