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


class NotificacoesResponse(BaseModel):
    itens: list[NotificacaoResponse]
    nao_vistas: int
    tem_mais: bool


class NotificacoesVistas(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[Annotated[int, Field(gt=0, strict=True)]] = Field(min_length=1, max_length=50)
