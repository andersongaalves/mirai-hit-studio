from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DashboardMetrics(BaseModel):
    clientes_ativos: int = Field(ge=0)
    orcamentos_abertos: int = Field(ge=0)
    propostas_aguardando_decisao: int = Field(ge=0)
    producoes_ativas: int = Field(ge=0)
    producoes_atrasadas: int = Field(ge=0)


class DashboardPipeline(BaseModel):
    orcamentos_abertos: int = Field(ge=0)
    propostas_enviadas: int = Field(ge=0)
    propostas_aprovadas: int = Field(ge=0)
    producoes_ativas: int = Field(ge=0)


class DashboardAttention(BaseModel):
    producoes_atrasadas: int = Field(ge=0)
    propostas_aguardando_decisao: int = Field(ge=0)


class DashboardActivity(BaseModel):
    tipo: Literal[
        "cliente_criado",
        "orcamento_criado",
        "proposta_enviada",
        "proposta_aprovada",
        "producao_criada",
    ]
    titulo: str
    data: datetime
    secao: Literal["section-clientes", "section-orcamentos", "section-producoes"]


class DashboardResponse(BaseModel):
    metrics: DashboardMetrics
    pipeline: DashboardPipeline
    attention: DashboardAttention
    recent_activity: list[DashboardActivity]
