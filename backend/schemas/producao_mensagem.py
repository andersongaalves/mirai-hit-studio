from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MensagemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: str = Field(min_length=1, max_length=4000)
    audiencia: Literal["todos", "equipe"] = "todos"
    responde_a_id: int | None = Field(default=None, ge=1)
    arquivo_id: int | None = Field(default=None, ge=1)


class MensagemArquivo(BaseModel):
    id: int
    nome_exibicao: str
    tipo: str
    versao: int


class MensagemResponse(BaseModel):
    id: int
    producao_id: int
    autor_papel: Literal["cliente", "produtor", "admin"]
    enviado_por_mim: bool
    audiencia: Literal["todos", "equipe"]
    texto: str
    responde_a_id: int | None
    arquivo: MensagemArquivo | None
    created_at: datetime
