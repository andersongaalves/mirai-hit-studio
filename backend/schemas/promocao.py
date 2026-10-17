"""Catalog promotions: explicit activation and optional, timezone-aware validity."""
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Promocao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ativa: bool = False
    percentual: Annotated[Decimal, Field(gt=0, lt=100, max_digits=5, decimal_places=2, allow_inf_nan=False)]
    inicio: AwareDatetime | None = None
    fim: AwareDatetime | None = None

    @model_validator(mode="after")
    def intervalo(self):
        if self.inicio is not None and self.fim is not None and self.fim <= self.inicio:
            raise ValueError("O fim da promocao deve ser posterior ao inicio.")
        return self


def validar_preco(base, promocao):
    if promocao and promocao.ativa:
        total = (Decimal(str(base)) * (1 - promocao.percentual / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if total <= 0:
            raise ValueError("A promocao deve manter um preco de pelo menos R$ 0,01.")


class PrecoCatalogo(BaseModel):
    preco_vigente: Decimal
    desconto_percentual: Decimal
    promocao_ativa: bool


class SnapshotPrecoCatalogo(PrecoCatalogo):
    promocao: Promocao | None = None
