"""Explicit service rights, never a withdrawable money balance."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreditoServico(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    unidade: Literal["faixa", "canal", "hora"]
    quantidade: Decimal = Field(gt=0, le=1000000, max_digits=12, decimal_places=3)

    @model_validator(mode="after")
    def unidades_discretas(self):
        if self.unidade != "hora" and self.quantidade != self.quantidade.to_integral_value():
            raise ValueError("Faixas e canais devem ter quantidade inteira.")
        return self


class CreditoContratado(CreditoServico):
    linha: int = Field(ge=1)
    componente: int = Field(ge=0)
    servico_id: int = Field(gt=0)
    servico_nome: str = Field(min_length=1, max_length=100)
    valor_centavos: int = Field(ge=0, le=2147483647)


class ContratoCreditos(BaseModel):
    model_config = ConfigDict(extra="forbid")
    versao: Literal[1] = 1
    itens: list[CreditoContratado] = Field(min_length=1, max_length=4000)


class CreditoSaldo(BaseModel):
    servico_id: int
    servico_nome: str
    unidade: Literal["faixa", "canal", "hora"]
    disponivel: Decimal = Field(ge=0, allow_inf_nan=False)
    bloqueado: Decimal = Field(ge=0, allow_inf_nan=False)


class CreditoLoteResponse(BaseModel):
    id: int
    proposta_id: int | None
    servico_nome: str
    unidade: Literal["faixa", "canal", "hora"]
    quantidade: Decimal = Field(gt=0, allow_inf_nan=False)
    estado: Literal["disponivel", "bloqueado"]
    created_at: datetime


class CarteiraCreditosResponse(BaseModel):
    saldos: list[CreditoSaldo]
    lotes: list[CreditoLoteResponse]
