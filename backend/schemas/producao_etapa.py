"""Contract stages of a production (Roadmap 3.0, 5.06)."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

StatusEtapa = Literal["pendente", "em_andamento", "em_revisao", "concluida"]


class EtapaProducaoResponse(BaseModel):
    id: int
    ordem: int
    item_indice: int
    item_descricao: str
    ordem_no_item: int
    nome: str
    status: StatusEtapa
    prazo: datetime | None
    iniciada_em: datetime | None
    concluida_em: datetime | None
    depende_da_anterior: bool
    administrativa: bool
    # Team-only fields (admin and producer).
    unidade: str | None = None
    revisoes_incluidas: int | None = None
    revisoes_usadas: int | None = None  # 5.10
    prazo_dias: int | None = None
    acoes: list[StatusEtapa] | None = None
    bloqueio_creditos: str | None = None
    # Admin-only contract economics.
    servico_id: int | None = None
    peso_percentual: Decimal | None = None
    valor: Decimal | None = None
    responsavel_usuario_id: int | None = None
    responsavel_nome: str | None = None
    executor_usuario_id: int | None = None
    executor_nome: str | None = None
    # Producer-only view of responsibility (5.07): never other producers' identities.
    minha: bool | None = None
    responsavel_rotulo: str | None = None


class EtapasProducaoResponse(BaseModel):
    producao_id: int
    progresso_percentual: int
    etapas: list[EtapaProducaoResponse]
    pode_gerar: bool | None = None
    etapas_ocultas: bool | None = None  # 5.10: client view hidden by contract policy.
    revisoes_excedentes: str | None = None  # 5.10: team view of the review policy.


class EtapaStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StatusEtapa
    status_atual: StatusEtapa


class EtapaAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StatusEtapa | None = None
    status_atual: StatusEtapa | None = None
    prazo: datetime | None = None


class EtapaResponsavelUpdate(BaseModel):
    """Roadmap 5.07: (re)assign the stage responsible; null leaves it unassigned."""

    model_config = ConfigDict(extra="forbid")

    responsavel_usuario_id: int | None = Field(default=None, gt=0)
    responsavel_atual: int | None = Field(default=None, gt=0)
    motivo: str = Field(default="", max_length=300)


class EtapaAtribuicaoResponse(BaseModel):
    id: int
    anterior_usuario_id: int | None
    anterior_nome: str | None
    novo_usuario_id: int | None
    novo_nome: str | None
    atribuido_por_nome: str | None
    motivo: str
    created_at: datetime | None
