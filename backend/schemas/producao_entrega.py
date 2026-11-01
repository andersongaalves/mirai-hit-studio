from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.producao_arquivo import ProducaoArquivoResponse


class ProducaoEntregaFinalResponse(BaseModel):
    id: int
    producao_id: int
    categoria: Literal["instrumental", "outro"]
    titulo: str
    etapa_id: int | None = None
    bpm: int | None
    tonalidade: str | None
    creditos_adicionais: list[str]
    observacao: str | None
    arquivo_principal: ProducaoArquivoResponse
    wav_arquivo: ProducaoArquivoResponse | None
    multitrack_arquivo: ProducaoArquivoResponse | None
    multitrack_disponivel: bool
    licenca_arquivo: ProducaoArquivoResponse | None
    bloqueado_pagamento: bool = False
    created_at: datetime


class ProducaoEntregaFinalUpdate(BaseModel):
    """Only the fields sent are changed; files are replaced by sending a new delivery."""

    model_config = ConfigDict(extra="forbid")

    titulo: str | None = Field(default=None, min_length=1, max_length=150)
    observacao: str | None = Field(default=None, max_length=1000)
    etapa_id: int | None = Field(default=None, gt=0)
    bpm: int | None = Field(default=None, ge=20, le=300)
    tonalidade: str | None = Field(default=None, max_length=20)
    creditos_adicionais: list[str] | None = Field(default=None, max_length=10)
