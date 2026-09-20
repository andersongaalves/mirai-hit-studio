from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FinanceiroAdminContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FinanceiroResumo(FinanceiroAdminContract):
    valor_a_receber: Decimal
    valor_recebido: Decimal
    cobrancas_parciais: int = Field(ge=0)
    pagamentos_em_atencao: int = Field(ge=0)
    total_cobrancas: int = Field(ge=0)


class FinanceiroCobrancaItem(FinanceiroAdminContract):
    id: int
    proposta_id: int
    proposta_numero: str
    cliente_nome: str
    valor_total: Decimal
    valor_pago: Decimal
    saldo_pendente: Decimal
    status: str
    reconciliation_status: str | None
    vencimento: datetime | None
    created_at: datetime
    updated_at: datetime


class FinanceiroCobrancaPage(FinanceiroAdminContract):
    items: list[FinanceiroCobrancaItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    pages: int = Field(ge=0)


class FinanceiroPagamentoItem(FinanceiroAdminContract):
    id: int
    tipo: str
    valor: Decimal
    status: str
    metodo: str | None
    provider: str | None
    provider_order_id: str | None
    reconciliation_status: str | None
    reconciliation_reason: str | None
    aprovado_em: datetime | None
    reembolsado_em: datetime | None
    created_at: datetime
    updated_at: datetime


class FinanceiroCobrancaDetalhe(FinanceiroCobrancaItem):
    cliente_email: str | None
    checkout_url: str
    pagamentos: list[FinanceiroPagamentoItem]


class FinanceiroReconciliacaoResponse(FinanceiroAdminContract):
    payment_id: int
    previous_status: str
    current_status: str
    changed: bool
    outcome: str
