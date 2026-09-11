from datetime import datetime
from pydantic import BaseModel, EmailStr

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
    pass


# ===========================
# UPDATE
# ===========================


class OrcamentoStatusUpdate(BaseModel):
    status: OrcamentoStatus


class OrcamentoProdutorUpdate(BaseModel):
    produtor_id: int | None = None


class OrcamentoObservacoesUpdate(BaseModel):
    observacoes: str


# ===========================
# RESPONSE
# ===========================


class OrcamentoResponse(OrcamentoBase):
    id: int

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