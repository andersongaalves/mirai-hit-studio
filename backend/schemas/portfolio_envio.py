from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from schemas.projeto import FuncaoCredito, ProjetoCaseType, ProjetoVertical
from schemas.validation import http_url


class PortfolioEnvioDados(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    producao_id: int | None = Field(default=None, gt=0)
    titulo: str = Field(min_length=3, max_length=150)
    artista: str = Field(min_length=1, max_length=100)
    categoria: str = Field(min_length=1, max_length=100)
    descricao: str = Field(default="", max_length=20000)
    link_audio: str = Field(min_length=8, max_length=500)
    vertical: ProjetoVertical
    case_type: ProjetoCaseType
    funcao: FuncaoCredito = "producao"
    funcao_outra: str | None = Field(default=None, min_length=1, max_length=60)
    autorizacao_artista: Literal[True]

    _audio_url = field_validator("link_audio")(http_url)

    @field_validator("autorizacao_artista", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("artist_consent_required")
        return value

    @model_validator(mode="after")
    def validate_role(self):
        if self.funcao == "outra" and not self.funcao_outra:
            raise ValueError("credit_other_role_required")
        if self.funcao != "outra":
            self.funcao_outra = None
        return self

    @field_validator("titulo", "artista", "categoria", "funcao_outra")
    @classmethod
    def normalize(cls, value):
        if value is None:
            return value
        value = " ".join(value.split())
        if not value:
            raise ValueError("required_text")
        return value


class PortfolioEnvioCreate(PortfolioEnvioDados):
    link_capa: str = Field(min_length=8, max_length=500)

    _cover_url = field_validator("link_capa")(http_url)


class PortfolioEnvioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    produtor_id: int
    producao_id: int | None
    dados: dict
    status: Literal["pendente", "aprovado", "recusado"]
    versao: int
    autorizado_em: datetime
    created_at: datetime
    revisado_em: datetime | None
    projeto_id: int | None
    motivo: str | None

    @field_serializer("dados")
    def public_data(self, value):
        return {key: item for key, item in value.items() if not key.startswith("_")}


class PortfolioEnvioRevisao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    versao: int = Field(ge=1)
    decisao: Literal["aprovar", "recusar"]
    motivo: str | None = Field(default=None, min_length=3, max_length=500)
