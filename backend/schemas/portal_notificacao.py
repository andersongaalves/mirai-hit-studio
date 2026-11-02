from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class NotificacaoResponse(BaseModel):
    id: int
    tipo: str
    texto: str
    url: str
    created_at: datetime
    vista_em: datetime | None
    # What the event is about (production, file, beat) and a cover image when there is one.
    contexto: str | None = None
    miniatura: str | None = None


class AtividadeResponse(BaseModel):
    id: str
    tipo: str
    titulo: str
    detalhe: str
    estado: str
    progresso: float | None = None
    criado_em: datetime | None = None
    concluido_em: datetime | None = None
    url: str | None = None
    miniatura: str | None = None


class AtividadesResponse(BaseModel):
    itens: list[AtividadeResponse]
    ativas: int


class NotificacoesResponse(BaseModel):
    itens: list[NotificacaoResponse]
    nao_vistas: int
    tem_mais: bool


class NotificacoesVistas(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[Annotated[int, Field(gt=0, strict=True)]] = Field(min_length=1, max_length=50)
