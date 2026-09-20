import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.validation import http_url


ProjetoVertical = Literal["artists", "creators", "media_games"]
ProjetoCaseType = Literal["client_case", "demo", "concept_project", "study"]
SEGMENTO_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,39}$")


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
    pass


class ProjetoResponse(ProjetoBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
