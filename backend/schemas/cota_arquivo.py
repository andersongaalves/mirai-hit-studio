"""File quotas per contract (Roadmap 3.0, 5.09)."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from services.producao_arquivo_storage import ALLOWED_MIME_TYPES

TipoCota = Literal["material", "referencia", "previa", "entrega"]


class CotaArquivo(BaseModel):
    """Limits for one file type. Every null field means "no contractual limit"."""

    model_config = ConfigDict(extra="forbid")

    tipo: TipoCota
    max_arquivos: int | None = Field(default=None, ge=1, le=100)  # Logical files (version groups).
    max_versoes: int | None = Field(default=None, ge=1, le=50)  # Versions per logical file.
    max_tamanho_mb: int | None = Field(default=None, ge=1, le=50)  # Per uploaded file.
    max_total_mb: int | None = Field(default=None, ge=1, le=5000)  # Physical storage of the type.
    formatos: list[str] | None = Field(default=None, max_length=20)

    @field_validator("formatos")
    @classmethod
    def known_formats(cls, value):
        if value is None:
            return None
        cleaned = sorted(set(value))
        if not cleaned or set(cleaned) - ALLOWED_MIME_TYPES:
            raise ValueError("formato_nao_permitido")
        return cleaned


class CotasUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cotas: list[CotaArquivo] = Field(default_factory=list, max_length=4)

    @field_validator("cotas")
    @classmethod
    def unique_types(cls, value):
        if len({cota.tipo for cota in value}) != len(value):
            raise ValueError("tipo_repetido")
        return value


class CotaUso(CotaArquivo):
    origem: Literal["contrato", "admin"] | None = None
    arquivos_usados: int = 0
    total_usado_bytes: int = 0


class CotasProducaoResponse(BaseModel):
    producao_id: int
    cotas: list[CotaUso]
    formatos_disponiveis: list[str]
