from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

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
    visivel_cliente: bool = Field(validation_alias=AliasChoices("visibilidade_cliente_efetiva", "visivel_cliente"))
    observacao: str | None = None
    processamento_tag: str | None = None
    created_at: datetime
    updated_at: datetime


class ProducaoArquivoVisibilidadeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visivel_produtor: bool
    visivel_cliente: bool


class ProducaoArquivoObservacaoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observacao: str | None = Field(default=None, max_length=1000)
