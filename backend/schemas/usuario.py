from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)

UsuarioRole = Literal["admin", "produtor", "cliente"]
Especialidade = Literal["beatmaker", "mixagem", "masterizacao"]
ESPECIALIDADES = ("beatmaker", "mixagem", "masterizacao")


def validar_cpf(value: str | None) -> str | None:
    """Digits only, with valid check digits; blank means none."""
    if value is None:
        return None
    digits = "".join(char for char in value if char.isdigit())
    if not digits:
        return None
    if len(digits) != 11 or len(set(digits)) == 1:
        raise ValueError("cpf_invalido")
    for size in (9, 10):
        total = sum(int(digit) * weight for digit, weight in zip(digits[:size], range(size + 1, 1, -1)))
        if (total * 10 % 11) % 10 != int(digits[size]):
            raise ValueError("cpf_invalido")
    return digits


def normalizar_especialidades(value):
    if value is None:
        return None
    chosen = set(value)
    return [item for item in ESPECIALIDADES if item in chosen]


def especialidades_lista(value):
    if isinstance(value, str):
        return [item for item in value.split(",") if item in ESPECIALIDADES]
    return list(value or [])


def validar_username(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("username_required")
    return value


def validar_nome_exibicao(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    return value or None


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
    nome_exibicao: str | None = Field(default=None, max_length=80)
    password: str = Field(min_length=8, max_length=72)
    role: UsuarioRole = "produtor"
    cliente_id: int | None = Field(default=None, gt=0)
    painel_beats: StrictBool = False
    # AUD6-S02-004: recovery e-mail for studio accounts (admin and producers).
    email: EmailStr | None = Field(default=None, max_length=150)
    especialidades: list[Especialidade] = Field(default_factory=list, max_length=3)
    # Required only for beatmakers (licensor of the beat contracts).
    cpf: str | None = Field(default=None, max_length=20)

    @field_validator("especialidades")
    @classmethod
    def especialidades_validas(cls, value):
        return normalizar_especialidades(value)

    @field_validator("cpf")
    @classmethod
    def cpf_valido(cls, value):
        return validar_cpf(value)

    @field_validator("email", mode="before")
    @classmethod
    def email_vazio(cls, value):
        return value.strip().lower() or None if isinstance(value, str) else value

    @field_validator("username")
    @classmethod
    def username_valido(cls, value: str) -> str:
        return validar_username(value)

    @field_validator("nome_exibicao")
    @classmethod
    def nome_exibicao_valido(cls, value):
        return validar_nome_exibicao(value)

    @field_validator("password")
    @classmethod
    def password_valido(cls, value: str) -> str:
        return validar_senha(value)

    @model_validator(mode="after")
    def vinculo_cliente_valido(self):
        if self.role == "cliente" and self.cliente_id is None:
            raise ValueError("client_link_required")
        if self.role != "cliente" and self.cliente_id is not None:
            raise ValueError("client_link_forbidden")
        if self.painel_beats and self.role != "produtor":
            raise ValueError("beat_panel_requires_producer")
        return self


class UsuarioUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = Field(default=None, min_length=1, max_length=50)
    # Null or blank clears it (the username is shown instead).
    nome_exibicao: str | None = Field(default=None, max_length=80)
    role: UsuarioRole | None = None
    ativo: StrictBool | None = None
    cliente_id: int | None = Field(default=None, gt=0)
    painel_beats: StrictBool | None = None
    # Null or blank removes the recovery e-mail.
    email: EmailStr | None = Field(default=None, max_length=150)
    especialidades: list[Especialidade] | None = Field(default=None, max_length=3)
    cpf: str | None = Field(default=None, max_length=20)

    @field_validator("especialidades")
    @classmethod
    def especialidades_validas(cls, value):
        return normalizar_especialidades(value)

    @field_validator("cpf")
    @classmethod
    def cpf_valido(cls, value):
        return validar_cpf(value)

    @field_validator("email", mode="before")
    @classmethod
    def email_vazio(cls, value):
        return value.strip().lower() or None if isinstance(value, str) else value

    @field_validator("nome_exibicao")
    @classmethod
    def nome_exibicao_valido(cls, value):
        return validar_nome_exibicao(value)

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


class SenhaPropriaUpdate(BaseModel):
    """AUD6-S02-004: own password change, any logged-in account."""
    model_config = ConfigDict(extra="forbid")

    senha_atual: str = Field(min_length=1, max_length=72)
    nova_senha: str = Field(min_length=8, max_length=72)

    @field_validator("nova_senha")
    @classmethod
    def password_valido(cls, value: str) -> str:
        return validar_senha(value)


class UsuarioResponse(BaseModel):

    id: int
    username: str
    nome_exibicao: str | None = None
    role: str
    is_admin: bool
    ativo: bool
    is_test: bool = False
    painel_beats: bool = False
    cliente_id: int | None
    email: str | None = None
    especialidades: list[str] = []
    # Lists only say whether the CPF is on file; the number stays in the detail.
    cpf_cadastrado: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("especialidades", mode="before")
    @classmethod
    def especialidades_csv(cls, value):
        return especialidades_lista(value)

    @model_validator(mode="wrap")
    @classmethod
    def marcar_cpf(cls, value, handler):
        result = handler(value)
        result.cpf_cadastrado = bool(getattr(value, "cpf", None) or (value.get("cpf") if isinstance(value, dict) else None))
        return result


class UsuarioDetalheResponse(UsuarioResponse):
    """Admin detail of one account: includes the beatmaker CPF."""

    cpf: str | None = None


class SessaoUsuarioResponse(BaseModel):
    """AUD6-S02-012: what the browser needs about the signed-in account, by role."""

    id: int
    username: str
    nome_exibicao: str | None = None
    role: str
    is_admin: bool
    ativo: bool
    # Only for clients (portal ownership) and producers (beats panel).
    cliente_id: int | None = None
    painel_beats: bool | None = None

    @classmethod
    def from_user(cls, usuario):
        role = usuario.role
        return cls(
            id=usuario.id,
            username=usuario.username,
            nome_exibicao=getattr(usuario, "nome_exibicao", None),
            role=role,
            is_admin=bool(getattr(usuario, "is_admin", False)),
            ativo=bool(getattr(usuario, "ativo", True)),
            cliente_id=getattr(usuario, "cliente_id", None) if role == "cliente" else None,
            painel_beats=bool(getattr(usuario, "painel_beats", False)) if role == "produtor" else None,
        )


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: SessaoUsuarioResponse
