"""Typed, validated portal settings (Roadmap 3.0, 5.01).

Only presentation parameters live here. Authentication, authorization, audit and
financial rules are never configurable (roadmap: Limites de seguranca e manutencao).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ClientIndicator = Literal["andamento", "concluidos", "avaliacao", "pagamentos"]
ProducerIndicator = Literal["ativas", "revisao", "vencidos", "a_receber", "pago"]


def _clean_text(value: str) -> str:
    cleaned = "".join(
        character for character in value
        if character == "\n" or (ord(character) >= 32 and ord(character) != 127)
    )
    return cleaned.strip()


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PortalAviso(_Strict):
    ativo: bool = False
    nivel: Literal["info", "atencao"] = "info"
    texto: str = Field(default="", max_length=280)

    @field_validator("texto")
    @classmethod
    def _texto(cls, value):
        return _clean_text(value)


def _unique_indicators(values):
    if not values:
        raise ValueError("Selecione ao menos um indicador.")
    if len(set(values)) != len(values):
        raise ValueError("Indicadores repetidos.")
    return values


class ClienteTextos(_Strict):
    titulo_dashboard: str = Field(default="Seus projetos", min_length=1, max_length=80)
    descricao_dashboard: str = Field(
        default="Acompanhe o que está acontecendo e saiba quando precisa agir.", max_length=240
    )
    ajuda_arquivos: str = Field(default="", max_length=240)

    @field_validator("titulo_dashboard", "descricao_dashboard", "ajuda_arquivos")
    @classmethod
    def _texto(cls, value):
        return _clean_text(value)


class ClienteFiltros(_Strict):
    situacao_padrao: Literal["todos", "ativos", "concluidos", "revisao"] = "todos"
    ordenacao_padrao: Literal["recente", "prazo"] = "recente"


class ClienteAreas(_Strict):
    propostas: bool = True


class ClientePortalConfig(_Strict):
    aviso: PortalAviso = Field(default_factory=PortalAviso)
    textos: ClienteTextos = Field(default_factory=ClienteTextos)
    indicadores: list[ClientIndicator] = Field(
        default_factory=lambda: ["andamento", "concluidos", "avaliacao", "pagamentos"]
    )
    filtros: ClienteFiltros = Field(default_factory=ClienteFiltros)
    areas: ClienteAreas = Field(default_factory=ClienteAreas)

    @field_validator("indicadores")
    @classmethod
    def _indicadores(cls, value):
        return _unique_indicators(value)


class ProdutorTextos(_Strict):
    descricao_dashboard: str = Field(default="O que precisa da sua atenção hoje.", max_length=240)
    ajuda_financeiro: str = Field(
        default="Valores e pagamentos registrados pela administração.", max_length=240
    )

    @field_validator("descricao_dashboard", "ajuda_financeiro")
    @classmethod
    def _texto(cls, value):
        return _clean_text(value)


class ProdutorFiltros(_Strict):
    status_padrao: Literal[
        "todos", "aguardando_inicio", "em_producao", "revisao", "finalizado", "entregue"
    ] = "todos"
    ordenacao_padrao: Literal["prazo", "recente"] = "prazo"


class ProdutorPortalConfig(_Strict):
    aviso: PortalAviso = Field(default_factory=PortalAviso)
    textos: ProdutorTextos = Field(default_factory=ProdutorTextos)
    indicadores: list[ProducerIndicator] = Field(
        default_factory=lambda: ["ativas", "revisao", "vencidos", "a_receber", "pago"]
    )
    filtros: ProdutorFiltros = Field(default_factory=ProdutorFiltros)

    @field_validator("indicadores")
    @classmethod
    def _indicadores(cls, value):
        return _unique_indicators(value)


class PortalConfigResponse(BaseModel):
    portal: Literal["cliente", "produtor"]
    versao: int
    config: dict


class PortalConfigAdminResponse(PortalConfigResponse):
    padrao: dict


class PortalConfigVersion(BaseModel):
    versao: int
    autor_usuario_id: int | None
    restaurada_de_versao: int | None
    created_at: str


class PortalConfigPublishRequest(_Strict):
    base_versao: int = Field(ge=0)
    config: dict


class PortalConfigRestoreRequest(_Strict):
    base_versao: int = Field(ge=0)
