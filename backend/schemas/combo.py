"""Catalog combos (Roadmap 3.0, 5.08)."""
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

Money = Annotated[Decimal, Field(ge=0, le=Decimal("9999999999.99"), max_digits=12, decimal_places=2, allow_inf_nan=False)]


class ComboWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=3, max_length=100)
    descricao: str = Field(default="", max_length=300)
    preco_base: Money
    ativo: bool = True
    servicos: list[Annotated[int, Field(gt=0)]] = Field(min_length=2, max_length=10)

    @field_validator("nome", "descricao")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("servicos")
    @classmethod
    def unique_services(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("servico_repetido")
        return value


class ComboServico(BaseModel):
    servico_id: int
    nome: str
    valor_base: Decimal
    etapas: int


class ComboResponse(BaseModel):
    id: int
    nome: str
    descricao: str
    preco_base: Decimal
    ativo: bool
    soma_servicos: Decimal
    servicos: list[ComboServico]
    created_at: datetime | None
    updated_at: datetime | None
