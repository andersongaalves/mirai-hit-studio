from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from schemas.validation import http_url

from core.enums import OrcamentoStatus


# ===========================
# BASE
# ===========================


class OrcamentoBase(BaseModel):
    nome_cliente: str
    email: EmailStr
    whatsapp: str | None = None

    servico: str
    valor_total: float

    link_guia: str | None = None
    detalhes: str | None = None


# ===========================
# CREATE
# ===========================


class OrcamentoCreate(OrcamentoBase):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    nome_cliente: str = Field(min_length=1, max_length=120)
    email: EmailStr = Field(max_length=150)
    whatsapp: str | None = Field(default=None, max_length=30)
    servico: str = Field(min_length=1, max_length=100)
    valor_total: float = Field(ge=0)
    link_guia: str | None = Field(default=None, max_length=500)
    detalhes: str | None = Field(default=None, max_length=20000)
    _url = field_validator("link_guia")(http_url)

    @field_validator("nome_cliente", "servico")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("field_required")
        return value.strip()


# ===========================
# UPDATE
# ===========================


class OrcamentoStatusUpdate(BaseModel):
    status: OrcamentoStatus


class OrcamentoProdutorUpdate(BaseModel):
    produtor_id: int | None = Field(default=None, gt=0, strict=True)


class OrcamentoObservacoesUpdate(BaseModel):
    observacoes: str = Field(max_length=20000)


# ===========================
# RESPONSE
# ===========================


class OrcamentoResponse(OrcamentoBase):
    id: int
    cliente_id: int | None

    # CRM
    status: OrcamentoStatus
    produtor_id: int | None
    observacoes: str

    # Proposta
    proposta_codigo: str | None
    proposta_pdf: str | None
    proposta_enviada: bool
    proposta_enviada_em: datetime | None

    # Datas
    data_solicitacao: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
