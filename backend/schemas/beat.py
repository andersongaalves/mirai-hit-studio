from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BeatCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    titulo: str = Field(min_length=1, max_length=160)
    descricao: str = Field(default="", max_length=5000)
    bpm: int | None = Field(default=None, ge=30, le=300)
    tonalidade: str | None = Field(default=None, max_length=24)
    generos: str = Field(default="", max_length=240)
    preco_lease: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )
    preco_exclusivo: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )

    @model_validator(mode="after")
    def algum_preco(self):
        if self.preco_lease is None and self.preco_exclusivo is None:
            raise ValueError("beat_price_required")
        return self


class BeatReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decisao: Literal["aprovar", "rejeitar"]
    motivo: str = Field(default="", max_length=500)


class BeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    licenca: Literal["lease", "exclusivo"]


class BeatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    produtor_id: int
    produtor: str
    titulo: str
    descricao: str
    bpm: int | None
    tonalidade: str | None
    generos: str
    preco_lease: Decimal | None
    preco_exclusivo: Decimal | None
    status: str
    ativo: bool
    motivo_rejeicao: str | None
    created_at: datetime
