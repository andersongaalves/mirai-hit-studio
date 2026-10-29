from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from schemas.producao_arquivo import ProducaoArquivoResponse


class ProducaoEntregaFinalResponse(BaseModel):
    id: int
    producao_id: int
    categoria: Literal["instrumental", "outro"]
    titulo: str
    observacao: str | None
    arquivo_principal: ProducaoArquivoResponse
    wav_arquivo: ProducaoArquivoResponse | None
    multitrack_arquivo: ProducaoArquivoResponse | None
    multitrack_disponivel: bool
    licenca_arquivo: ProducaoArquivoResponse | None
    bloqueado_pagamento: bool = False
    created_at: datetime
