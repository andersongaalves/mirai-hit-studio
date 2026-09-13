"""Contracts only; financial authority belongs to the future service."""
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator
from models.enums.proposta import PropostaStatus
from schemas.validation import http_url

Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Quantity = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
PositiveId = Annotated[int, Field(gt=0, strict=True)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PropostaItem(Contract):
    descricao: str = Field(max_length=10000)
    quantidade: Quantity
    valor_unitario: Money
    desconto: Money = Decimal("0")  # Absolute discount per line, as in the editor.


class PropostaPagamento(Contract):
    tipo: str = Field(min_length=1, max_length=40)
    titulo: str = Field(min_length=1, max_length=200)
    url: str = Field(default="", max_length=2000)
    habilitado: bool = False

    @field_validator("url")
    @classmethod
    def http_url(cls, value):
        if value:
            http_url(value)
        return value

    @field_validator("habilitado")
    @classmethod
    def enabled_requires_url(cls, value, info):
        if value and not info.data.get("url"):
            raise ValueError("enabled_payment_requires_url")
        return value


class PropostaTotais(Contract):
    subtotal: Money
    desconto: Money
    total: Money


class ClienteSnapshot(Contract):
    nome: str
    email: str
    whatsapp: str | None = None


class OrcamentoSnapshot(Contract):
    id: PositiveId
    servico: str
    detalhes: str | None = None
    valor_total: Decimal | None = Field(default=None, allow_inf_nan=False)
    link_guia: str | None = None


class PropostaSnapshot(Contract):
    cliente: ClienteSnapshot
    orcamento: OrcamentoSnapshot


class PropostaCreate(Contract):
    """Empty body: the future action obtains the budget from URL/context."""


class PropostaUpdate(Contract):
    produtor_id: PositiveId | None = None
    objeto: str | None = Field(default=None, max_length=200)
    descricao: str | None = Field(default=None, max_length=50000)
    itens: list[PropostaItem] | None = Field(default=None, max_length=200)
    pagamentos: list[PropostaPagamento] | None = Field(default=None, max_length=20)
    condicoes: str | None = Field(default=None, max_length=50000)

    @field_validator("objeto", "descricao", "itens", "pagamentos", "condicoes")
    @classmethod
    def non_nullable_when_present(cls, value):
        if value is None:
            raise ValueError("field_cannot_be_null")
        return value

    @field_validator("pagamentos")
    @classmethod
    def unique_payment_types(cls, value):
        if len({payment.tipo for payment in value}) != len(value):
            raise ValueError("duplicate_payment_type")
        return value


class PropostaResponse(Contract):
    id: PositiveId
    orcamento_id: PositiveId
    numero: str = Field(max_length=30)
    versao: int = Field(ge=1)
    status: PropostaStatus
    produtor_id: PositiveId | None
    cliente_snapshot: PropostaSnapshot
    objeto: str = Field(max_length=200)
    descricao: str
    itens: list[PropostaItem]
    pagamentos: list[PropostaPagamento]
    condicoes: str
    totais: PropostaTotais | None
    pdf_path: str | None = Field(max_length=500)
    gerada_em: datetime | None
    enviada_em: datetime | None
    aprovada_em: datetime | None
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_orm_model(cls, proposta):
        mapping = {"itens": "itens_json", "pagamentos": "pagamentos_json", "totais": "totais_json"}
        data = {name: getattr(proposta, mapping.get(name, name)) for name in cls.model_fields}
        if data["totais"] == {}:
            data["totais"] = None  # Not calculated yet, not an authoritative zero.
        return cls.model_validate(data)
