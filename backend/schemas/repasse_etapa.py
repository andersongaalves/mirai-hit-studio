from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RepasseEtapaResponse(BaseModel):
    id: int | None
    etapa_id: int
    etapa_nome: str
    producao_id: int
    producao_titulo: str
    produtor_id: int | None
    bruto_centavos: int
    produtor_centavos: int
    mirai_centavos: int
    estado: Literal["previsto", "bloqueado", "a_receber", "pago"]
    bloqueio: str | None
    pago_em: datetime | None
    comprovante_arquivo_id: int | None


class RepasseEtapaPagamento(BaseModel):
    model_config = ConfigDict(extra="forbid")
    referencia: str = Field(min_length=3, max_length=160)
    comprovante_arquivo_id: int | None = Field(default=None, gt=0, strict=True)
    idempotency_key: UUID

    @field_validator("referencia")
    @classmethod
    def referencia_valida(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("payment_reference_required")
        return value
