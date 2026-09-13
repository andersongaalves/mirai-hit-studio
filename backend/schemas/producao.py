import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


StatusProducao = Literal[
    "aguardando_inicio",
    "em_producao",
    "revisao",
    "finalizado",
    "entregue",
]


def validar_etapas_json(value: str) -> str:
    if len(value) > 20_000:
        raise ValueError("etapas_excedem_limite")
    try:
        etapas = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        raise ValueError("etapas_json_invalido") from None
    if not isinstance(etapas, list) or len(etapas) > 50:
        raise ValueError("etapas_invalidas")

    normalizadas = []
    for etapa in etapas:
        if not isinstance(etapa, dict) or set(etapa) - {"nome", "feito"}:
            raise ValueError("etapa_invalida")
        nome = etapa.get("nome")
        feito = etapa.get("feito", False)
        if not isinstance(nome, str) or not nome.strip() or len(nome.strip()) > 120:
            raise ValueError("nome_etapa_invalido")
        if not isinstance(feito, bool):
            raise ValueError("estado_etapa_invalido")
        normalizadas.append({"nome": nome.strip(), "feito": feito})

    return json.dumps(normalizadas, ensure_ascii=False)


class ProducaoBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    titulo: str = Field(min_length=1, max_length=150)
    cliente: str = Field(min_length=1, max_length=120)
    servico: str = Field(min_length=1, max_length=100)
    observacoes: str = Field(default="", max_length=20_000)
    etapas: str = "[]"

    @field_validator("titulo", "cliente", "servico")
    @classmethod
    def texto_obrigatorio(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("texto_obrigatorio")
        return value

    @field_validator("etapas")
    @classmethod
    def etapas_validas(cls, value: str) -> str:
        return validar_etapas_json(value)


class ProducaoCreate(ProducaoBase):
    produtor_id: int | None = Field(default=None, gt=0)
    orcamento_id: int | None = Field(default=None, gt=0)


class ProducaoStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: StatusProducao


class ProducaoEtapasUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    etapas: str

    @field_validator("etapas")
    @classmethod
    def etapas_validas(cls, value: str) -> str:
        return validar_etapas_json(value)


class ProducaoPrazoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prazo_entrega: datetime | None


class ProducaoObservacoesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observacoes: str = Field(default="", max_length=20_000)


class ProducaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    cliente: str
    servico: str
    status: str
    produtor_id: int | None
    produtor_nome: str | None = None
    orcamento_id: int | None
    proposta_id: int | None = None
    proposta_numero: str | None = None
    cliente_email: str | None = None
    observacoes: str
    etapas: str
    prazo_entrega: datetime | None
    created_at: datetime
    updated_at: datetime
