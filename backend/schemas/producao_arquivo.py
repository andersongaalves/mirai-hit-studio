from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

TipoArquivoProducao = Literal[
    "material",
    "referencia",
    "previa",
    "entrega",
    "comprovante",
]


class ProducaoArquivoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    producao_id: int
    remetente_usuario_id: int | None
    tipo: TipoArquivoProducao
    nome_exibicao: str
    mime_type: str
    tamanho_bytes: int
    sha256: str
    grupo_versao: str
    versao: int
    substitui_arquivo_id: int | None
    visivel_produtor: bool
    visivel_cliente: bool
    created_at: datetime
    updated_at: datetime


class ProducaoArquivoVisibilidadeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visivel_produtor: bool
    visivel_cliente: bool
