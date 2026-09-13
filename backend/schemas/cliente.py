from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class ClienteBase(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    nome: str = Field(min_length=1, max_length=120)
    email: EmailStr | None = Field(default=None, max_length=150)
    telefone: str | None = Field(default=None, max_length=30)
    observacoes: str = Field(default="", max_length=20_000)
    ativo: bool = True

    @field_validator("nome")
    @classmethod
    def nome_valido(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("nome_obrigatorio")
        return value

    @field_validator("telefone")
    @classmethod
    def telefone_valido(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def contato_obrigatorio(self):
        if self.email is None and self.telefone is None:
            raise ValueError("contato_obrigatorio")
        return self


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = Field(default=None, max_length=150)
    telefone: str | None = Field(default=None, max_length=30)
    observacoes: str | None = Field(default=None, max_length=20_000)
    ativo: bool | None = None

    @field_validator("nome")
    @classmethod
    def nome_valido(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("campo_nao_nulo")
        value = value.strip()
        if not value:
            raise ValueError("nome_obrigatorio")
        return value

    @field_validator("observacoes", "ativo")
    @classmethod
    def campo_nao_nulo(cls, value):
        if value is None:
            raise ValueError("campo_nao_nulo")
        return value

    @field_validator("telefone")
    @classmethod
    def telefone_valido(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ClienteResponse(ClienteBase):
    id: int
    created_at: datetime
    updated_at: datetime


class ClienteSummary(ClienteResponse):
    total_orcamentos: int = 0
    ultima_interacao: datetime | None = None


class ClienteHistoricoItem(BaseModel):
    evento: str
    titulo: str
    data: datetime
    orcamento_id: int | None = None
    proposta_id: int | None = None
    producao_id: int | None = None


class ClienteDetail(ClienteResponse):
    total_orcamentos: int = 0
    historico: list[ClienteHistoricoItem] = Field(default_factory=list)
