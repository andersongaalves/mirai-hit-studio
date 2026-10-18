from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReservaCreditos(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    lote_id: int = Field(gt=0)
    quantidade: Decimal = Field(gt=0, le=1000000, max_digits=12, decimal_places=3)
    motivo: str = Field(min_length=5, max_length=500)
    idempotency_key: UUID


class MovimentoCreditos(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    tipo: Literal["consumo", "devolucao", "estorno"]
    motivo: str = Field(min_length=5, max_length=500)
    idempotency_key: UUID


class NovaProducaoCreditos(ReservaCreditos):
    titulo: str = Field(min_length=1, max_length=150)
    produtor_id: int = Field(gt=0)


class AlocacaoResponse(BaseModel):
    id: int
    producao_id: int
    lote_id: int
    servico_nome: str
    unidade: Literal["faixa", "canal", "hora"]
    quantidade: Decimal
    estado: Literal["reservada", "consumida", "devolvida", "estornada"]
    created_at: datetime
    valor_centavos: int


class LoteDisponivel(BaseModel):
    id: int
    servico_nome: str
    unidade: Literal["faixa", "canal", "hora"]
    disponivel: Decimal = Field(gt=0, allow_inf_nan=False)


class ContextoCreditos(BaseModel):
    producao_status: str
    pode_reservar: bool
    mensagem: str | None
    lotes: list[LoteDisponivel]
    alocacoes: list[AlocacaoResponse]
