"""Proposal contracts; financial authority remains in backend domain services."""
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from models.enums.proposta import PoliticaPagamento, PropostaStatus
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)

from schemas.credito_servico import ContratoCreditos
from schemas.promocao import SnapshotPrecoCatalogo
from schemas.validation import http_url

Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Quantity = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
PositiveId = Annotated[int, Field(gt=0, strict=True)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PropostaItem(Contract):
    descricao: str = Field(max_length=10000)
    quantidade: Quantity
    valor_unitario: Money  # Negotiated price; may differ from the catalog base price.
    desconto: Money = Decimal(0)  # Absolute discount per line, as in the editor.
    servico_id: PositiveId | None = None  # Roadmap 3.0, 5.05: optional catalog origin.
    combo_id: PositiveId | None = None  # Roadmap 3.0, 5.08: or a catalog combo (never both).
    beat_id: PositiveId | None = None
    licenca_beat: Literal["lease", "lease_mp3", "lease_wav", "multitrack", "exclusivo"] | None = None

    @field_validator("combo_id")
    @classmethod
    def service_or_combo(cls, value, info):
        if value is not None and info.data.get("servico_id") is not None:
            raise ValueError("servico_ou_combo")
        return value

    @model_validator(mode="after")
    def origem_unica(self):
        origins = sum(value is not None for value in (self.servico_id, self.combo_id, self.beat_id))
        if origins > 1:
            raise ValueError("catalog_origin_must_be_unique")
        if (self.beat_id is None) != (self.licenca_beat is None):
            raise ValueError("beat_license_required")
        if self.beat_id is not None and self.quantidade != 1:
            raise ValueError("beat_quantity_must_be_one")
        return self


class PropostaPagamento(Contract):
    tipo: str = Field(min_length=1, max_length=40)
    titulo: str = Field(min_length=1, max_length=200)
    url: str = Field(default="", max_length=2000)
    habilitado: bool = False

    @field_validator("url")
    @classmethod
    def http_url(cls, value):
        if value:
            http_url(value)
        return value

    @field_validator("habilitado")
    @classmethod
    def enabled_requires_url(cls, value, info):
        if value and not info.data.get("url"):
            raise ValueError("enabled_payment_requires_url")
        return value


class PropostaTotais(Contract):
    subtotal: Money
    desconto: Money
    total: Money


class SnapshotEtapa(Contract):
    ordem: int = Field(ge=1)
    nome: str
    peso_percentual: Decimal
    valor: Decimal
    prazo_dias: int | None
    unidade: str
    revisoes_incluidas: int | None
    depende_da_anterior: bool
    administrativa: bool
    # 5.08: stage origin inside a combo (absent for single-service items).
    servico_id: int | None = None
    servico_nome: str | None = None
    componente_indice: int | None = None


class SnapshotCota(Contract):
    """5.09: file quota of one type frozen with the contract."""
    tipo: str
    max_arquivos: int | None = None
    max_versoes: int | None = None
    max_tamanho_mb: int | None = None
    max_total_mb: int | None = None
    max_duracao_min: int | None = None
    formatos: list[str] | None = None


class SnapshotPoliticas(Contract):
    """5.10: portal policies of a service frozen with the contract."""
    publicacao_previa: str
    revisoes_excedentes: str
    cliente_ve_etapas: bool
    cliente_ve_prazos_etapas: bool
    financeiro_cliente: str
    entrega_final: Literal["apos_quitacao", "liberada"] = "apos_quitacao"
    produtor_ve_contato_cliente: bool = True


class SnapshotComponente(Contract):
    """5.08: share of a combo allocated to one component service."""
    indice: int = Field(ge=1)
    servico_id: int
    servico_nome: str
    preco_catalogo: Decimal
    valor_alocado: Decimal
    cotas_arquivos: list[SnapshotCota] | None = None  # 5.09
    politicas: SnapshotPoliticas | None = None  # 5.10


class SnapshotItem(Contract):
    indice: int = Field(ge=1)
    descricao: str
    servico_id: int | None
    servico_nome: str | None
    preco_catalogo: Decimal | None
    catalogo_disponivel: bool
    quantidade: Decimal
    valor_unitario: Decimal
    bruto: Decimal
    desconto: Decimal
    valor_contratado: Decimal
    etapas: list[SnapshotEtapa]
    combo_id: int | None = None
    combo_nome: str | None = None
    componentes: list[SnapshotComponente] = []
    cotas_arquivos: list[SnapshotCota] | None = None  # 5.09: absent before 5.09 and on free lines.
    politicas: SnapshotPoliticas | None = None  # 5.10: absent before 5.10 and on free lines.
    preco_catalogo_vigente: SnapshotPrecoCatalogo | None = None  # 5.17: context, never rewrites negotiated values.
    beat_id: int | None = None
    beat_titulo: str | None = None
    licenca_beat: Literal["lease", "lease_mp3", "lease_wav", "multitrack", "exclusivo"] | None = None


class SnapshotEconomico(Contract):
    """Economic contract frozen once; later catalog edits never rewrite it (5.05)."""
    versao_snapshot: Literal[1]
    proposta_versao: int = Field(ge=1)
    moeda: Literal["BRL"]
    origem: Literal["envio", "aceite"]
    congelado_em: datetime
    subtotal: Decimal
    desconto: Decimal
    total: Decimal
    itens: list[SnapshotItem]


class ClienteSnapshot(Contract):
    nome: str
    email: str
    whatsapp: str | None = None


class OrcamentoSnapshot(Contract):
    id: PositiveId
    servico: str
    detalhes: str | None = None
    valor_total: Decimal | None = Field(default=None, allow_inf_nan=False)
    link_guia: str | None = None


class PropostaSnapshot(Contract):
    cliente: ClienteSnapshot
    orcamento: OrcamentoSnapshot


class PropostaCreate(Contract):
    """Empty body: the future action obtains the budget from URL/context."""


class PropostaClassificacaoUpdate(Contract):
    is_test: StrictBool
    confirmar_historico_financeiro: StrictBool = False


class PropostaClassificacaoResponse(Contract):
    id: int
    orcamento_id: int
    is_test: bool
    protegida: bool
    historico_financeiro: bool
    reversao_permitida: bool


class PropostaUpdate(Contract):
    finalidade: Literal["producao", "creditos"] | None = None
    produtor_id: PositiveId | None = None
    objeto: str | None = Field(default=None, max_length=200)
    descricao: str | None = Field(default=None, max_length=50000)
    itens: list[PropostaItem] | None = Field(default=None, max_length=200)
    pagamentos: list[PropostaPagamento] | None = Field(default=None, max_length=20)
    politica_pagamento: PoliticaPagamento | None = None
    condicoes: str | None = Field(default=None, max_length=50000)

    @field_validator(
        "finalidade",
        "objeto",
        "descricao",
        "itens",
        "pagamentos",
        "politica_pagamento",
        "condicoes",
    )
    @classmethod
    def non_nullable_when_present(cls, value):
        if value is None:
            raise ValueError("field_cannot_be_null")
        return value

    @field_validator("pagamentos")
    @classmethod
    def unique_payment_types(cls, value):
        if len({payment.tipo for payment in value}) != len(value):
            raise ValueError("duplicate_payment_type")
        return value


class PropostaResponse(Contract):
    finalidade: Literal["producao", "creditos"] = "producao"
    contrato_creditos: ContratoCreditos | None = None
    id: PositiveId
    orcamento_id: PositiveId
    numero: str = Field(max_length=30)
    versao: int = Field(ge=1)
    status: PropostaStatus
    produtor_id: PositiveId | None
    cliente_snapshot: PropostaSnapshot
    objeto: str = Field(max_length=200)
    descricao: str
    itens: list[PropostaItem]
    pagamentos: list[PropostaPagamento]
    politica_pagamento: PoliticaPagamento
    condicoes: str
    totais: PropostaTotais | None
    snapshot_economico: SnapshotEconomico | None = None
    pdf_path: str | None = Field(max_length=500)
    gerada_em: datetime | None
    enviada_em: datetime | None
    aprovada_em: datetime | None
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_orm_model(cls, proposta):
        mapping = {"itens": "itens_json", "pagamentos": "pagamentos_json", "totais": "totais_json"}
        data = {name: getattr(proposta, mapping.get(name, name)) for name in cls.model_fields
                if name not in ("snapshot_economico", "finalidade", "contrato_creditos")}
        data["finalidade"] = getattr(proposta, "finalidade", None) or "producao"
        data["contrato_creditos"] = getattr(proposta, "contrato_creditos", None)
        # Optional 5.05 field: lightweight doubles without the column still serialize.
        data["snapshot_economico"] = getattr(proposta, "snapshot_economico", None)
        if data["totais"] == {}:
            data["totais"] = None  # Not calculated yet, not an authoritative zero.
        return cls.model_validate(data)
