import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from schemas.validation import http_url

ProjetoVertical = Literal["artists", "creators", "media_games"]
ProjetoCaseType = Literal["client_case", "demo", "concept_project", "study"]
SEGMENTO_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
FuncaoCredito = Literal["producao", "mixagem", "masterizacao", "composicao", "gravacao", "beat", "outra"]
MAX_CREDITOS = 20


class CreditoProjeto(BaseModel):
    """Roadmap 5.19: one credit; producers may be linked to their account, externals by name only."""
    model_config = ConfigDict(extra="forbid")

    funcao: FuncaoCredito
    funcao_outra: str | None = Field(default=None, max_length=60)
    nome: str = Field(..., min_length=1, max_length=100)
    usuario_id: int | None = Field(default=None, gt=0)

    @field_validator("nome", "funcao_outra")
    @classmethod
    def strip_text(cls, value):
        if value is None:
            return None
        value = " ".join(value.split())
        return value or None

    @model_validator(mode="after")
    def check_role(self):
        if not self.nome:
            raise ValueError("credit_name_required")
        if self.funcao == "outra" and not self.funcao_outra:
            raise ValueError("credit_other_role_required")
        if self.funcao != "outra":
            self.funcao_outra = None
        return self


class CreditoProjetoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    funcao: FuncaoCredito
    funcao_outra: str | None = None
    nome: str
    usuario_id: int | None = None


class CreditoProjetoPublico(BaseModel):
    """Public view: name and role only, never the account link."""
    model_config = ConfigDict(from_attributes=True)

    funcao: FuncaoCredito
    funcao_outra: str | None = None
    nome: str


class ProjetoBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    titulo: str = Field(..., min_length=3, max_length=150)
    artista: str = Field(..., min_length=1, max_length=150)
    categoria: str = Field(..., min_length=1, max_length=100)
    link_audio: str = Field(..., max_length=500)
    link_capa: str = Field(..., max_length=500)
    descricao: str = Field(..., max_length=20000)
    destaque: bool = False
    vertical: ProjetoVertical | None = None
    segmentos_json: list[str] = Field(default_factory=list, max_length=20)
    case_type: ProjetoCaseType | None = None
    show_mix_comparison_on_landing: bool = False
    landing_order: int | None = Field(default=None, ge=1, le=4)
    creditos: list[CreditoProjeto] = Field(default_factory=list, max_length=MAX_CREDITOS)

    _urls = field_validator("link_audio", "link_capa")(http_url)

    @field_validator("titulo", "artista", "categoria")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("required_text")
        return value

    @field_validator("segmentos_json")
    @classmethod
    def validate_segments(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("duplicate_segment")
        if any(not SEGMENTO_PATTERN.fullmatch(value) for value in values):
            raise ValueError("invalid_segment")
        return values


class ProjetoCreate(ProjetoBase):
    pass


class ProjetoUpdate(ProjetoBase):
    titulo: str | None = Field(default=None, min_length=3, max_length=150)
    artista: str | None = Field(default=None, min_length=1, max_length=150)
    categoria: str | None = Field(default=None, min_length=1, max_length=100)
    link_audio: str | None = Field(default=None, max_length=500)
    link_capa: str | None = Field(default=None, max_length=500)
    descricao: str | None = Field(default=None, max_length=20000)
    destaque: bool | None = None
    vertical: ProjetoVertical | None = None
    segmentos_json: list[str] | None = Field(default=None, max_length=20)
    case_type: ProjetoCaseType | None = None
    show_mix_comparison_on_landing: bool | None = None
    landing_order: int | None = Field(default=None, ge=1, le=4)
    creditos: list[CreditoProjeto] | None = Field(default=None, max_length=MAX_CREDITOS)

    @field_validator(
        "titulo",
        "artista",
        "categoria",
        "link_audio",
        "link_capa",
        "descricao",
        "destaque",
        "segmentos_json",
        "show_mix_comparison_on_landing",
        "creditos",
        mode="before",
    )
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            raise ValueError("field_cannot_be_null")
        return value


class ProjetoResponse(ProjetoBase):
    id: int
    audio_before_url: str | None = None
    audio_after_url: str | None = None
    creditos: list[CreditoProjetoResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class ProjetoPublicResponse(ProjetoResponse):
    creditos: list[CreditoProjetoPublico] = Field(default_factory=list)


class ProjetoMixComparisonPublic(BaseModel):
    id: int
    titulo: str
    artista: str
    link_capa: str
    link_audio: str
    audio_before_url: str
    audio_after_url: str
    landing_order: int
