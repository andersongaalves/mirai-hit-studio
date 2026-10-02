from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProducaoClienteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    servico: str
    status: str
    etapas: str
    prazo_entrega: datetime | None
    created_at: datetime
    updated_at: datetime


class PagamentoClienteResponse(BaseModel):
    tipo: str
    valor: Decimal
    status: str
    metodo: str | None
    aprovado_em: datetime | None
    created_at: datetime


class CobrancaClienteResponse(BaseModel):
    status: str
    valor_total: Decimal
    valor_pago: Decimal
    saldo_pendente: Decimal
    moeda: str
    vencimento: datetime | None
    pagamentos: list[PagamentoClienteResponse]


class FinanceiroClienteResponse(BaseModel):
    producao_id: int
    proposta_numero: str | None
    proposta_status: str | None
    cobranca: CobrancaClienteResponse | None
