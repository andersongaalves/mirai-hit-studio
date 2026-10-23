from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FinanceiroAdminContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FinanceiroResumo(FinanceiroAdminContract):
    valor_a_receber: Decimal
    valor_recebido: Decimal
    cobrancas_parciais: int = Field(ge=0)
    pagamentos_em_atencao: int = Field(ge=0)
    total_cobrancas: int = Field(ge=0)


class FinanceiroCobrancaItem(FinanceiroAdminContract):
    is_test: bool = False
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


class FinanceiroPagamentoManualRequest(FinanceiroAdminContract):
    modo: Literal["parcial", "quitar"]
    valor: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    referencia: str = Field(min_length=3, max_length=120)
    idempotency_key: UUID

    @model_validator(mode="after")
    def validar_valor(self):
        if self.modo == "parcial" and self.valor is None:
            raise ValueError("Informe o valor do pagamento parcial.")
        if self.modo == "quitar" and self.valor is not None:
            raise ValueError("A quitacao utiliza automaticamente o saldo pendente.")
        self.referencia = self.referencia.strip()
        if len(self.referencia) < 3:
            raise ValueError("Informe uma referencia valida para o Pix.")
        return self


class FinanceiroPagamentoManualResponse(FinanceiroAdminContract):
    payment_id: int
    cobranca_id: int
    valor: Decimal
    valor_pago: Decimal
    saldo_pendente: Decimal
    status: str
    repeated: bool = False
