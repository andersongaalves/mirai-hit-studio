"""Contract stages of a production (Roadmap 3.0, 5.06)."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

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
    prazo_dias: int | None = None
    acoes: list[StatusEtapa] | None = None
    # Admin-only contract economics.
    servico_id: int | None = None
    peso_percentual: Decimal | None = None
    valor: Decimal | None = None
    responsavel_usuario_id: int | None = None


class EtapasProducaoResponse(BaseModel):
    producao_id: int
    progresso_percentual: int
    etapas: list[EtapaProducaoResponse]
    pode_gerar: bool | None = None


class EtapaStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StatusEtapa
    status_atual: StatusEtapa


class EtapaAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StatusEtapa | None = None
    status_atual: StatusEtapa | None = None
    prazo: datetime | None = None
