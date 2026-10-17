"""Contractual portal policies (Roadmap 3.0, 5.10).

A closed, typed set of policies. Values inherit: production exception > contract (frozen
when the proposal is sent) > global default (versioned) > system default. A service only
overrides the keys it sets. Nothing here can turn off authentication, permissions or audit.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PublicacaoPrevia = Literal["automatica", "aprovacao_admin"]
RevisoesExcedentes = Literal["permitir", "exigir_admin"]
FinanceiroCliente = Literal["completo", "resumido"]
EntregaFinal = Literal["apos_quitacao", "liberada"]
Origem = Literal["excecao", "contrato", "global", "sistema"]


class PoliticasCompletas(BaseModel):
    """Every policy with its system default.

    entrega_final (5.14): final delivery files are downloadable only once the charge is paid
    in full; previews stay free. "liberada" releases them regardless of the balance.
    """
    model_config = ConfigDict(extra="forbid")

    publicacao_previa: PublicacaoPrevia = "automatica"
    revisoes_excedentes: RevisoesExcedentes = "permitir"
    cliente_ve_etapas: bool = True
    cliente_ve_prazos_etapas: bool = True
    financeiro_cliente: FinanceiroCliente = "completo"
    entrega_final: EntregaFinal = "apos_quitacao"


class PoliticasParciais(BaseModel):
    """Overrides: a missing or null key inherits from the level below."""
    model_config = ConfigDict(extra="forbid")

    publicacao_previa: PublicacaoPrevia | None = None
    revisoes_excedentes: RevisoesExcedentes | None = None
    cliente_ve_etapas: bool | None = None
    cliente_ve_prazos_etapas: bool | None = None
    financeiro_cliente: FinanceiroCliente | None = None
    entrega_final: EntregaFinal | None = None


class PoliticasGlobaisPublicar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    politicas: PoliticasCompletas
    base_versao: int = Field(ge=0)


class PoliticasGlobaisRestaurar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    versao: int = Field(ge=1)
    base_versao: int = Field(ge=0)


class PoliticaVersao(BaseModel):
    versao: int
    autor_usuario_id: int | None
    restaurada_de_versao: int | None
    created_at: str


class PoliticasGlobaisResponse(BaseModel):
    versao: int
    politicas: PoliticasCompletas
    padroes: PoliticasCompletas
    versoes: list[PoliticaVersao] = []


class PoliticasServicoResponse(BaseModel):
    servico_id: int
    politicas: PoliticasParciais
    herdadas: PoliticasCompletas  # Current global values, for the editor.


class ExcecaoPoliticas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    politicas: PoliticasParciais
    motivo: str = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def _alguma(self):
        if not self.politicas.model_dump(exclude_none=True):
            raise ValueError("Informe ao menos uma politica; para voltar ao contrato, remova a excecao.")
        self.motivo = self.motivo.strip()
        if len(self.motivo) < 5:
            raise ValueError("Explique o motivo da excecao.")
        return self


class PoliticasProducaoResponse(BaseModel):
    producao_id: int
    vigentes: PoliticasCompletas
    origens: dict[str, Origem]
    contrato: PoliticasCompletas | None
    excecao: PoliticasParciais | None
    motivo: str | None
    atualizado_em: datetime | None
