from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RepasseProdutorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    producao_id: int
    producao_titulo: str | None = None
    produtor_id: int
    produtor_nome: str | None = None
    valor_combinado: Decimal
    moeda: str
    status: Literal["definido", "liberado", "pago"]
    liberado_em: datetime | None
    pago_em: datetime | None
    referencia_pagamento: str | None
    comprovante_arquivo_id: int | None
    created_at: datetime
    updated_at: datetime


class RepasseDefinirRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valor_combinado: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class RepassePagamentoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    referencia_pagamento: str | None = Field(default=None, max_length=160)
    comprovante_arquivo_id: int | None = Field(default=None, gt=0)

    @field_validator("referencia_pagamento")
    @classmethod
    def normalizar_referencia(cls, value):
        value = value.strip() if value else None
        return value or None


class RepasseCorrecaoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valor_combinado: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=12,
        decimal_places=2,
    )
    referencia_pagamento: str | None = Field(default=None, max_length=160)
    comprovante_arquivo_id: int | None = Field(default=None, gt=0)

    @field_validator("referencia_pagamento")
    @classmethod
    def normalizar_referencia(cls, value):
        value = value.strip() if value else None
        return value or None
