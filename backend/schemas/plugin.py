import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])?$")
FORMATOS = ("VST3", "AU", "AAX", "CLAP", "Standalone")


def _clean(value):
    if value is None:
        return None
    value = " ".join(str(value).split()) if "\n" not in str(value) else str(value).strip()
    return value or None


class PluginPayload(BaseModel):
    """What the Admin edits on a plugin (installers and cover are sent separately)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: str = Field(min_length=2, max_length=80)
    slug: str = Field(min_length=1, max_length=60)
    tagline: str | None = Field(default=None, max_length=160)
    descricao: str | None = Field(default=None, max_length=8000)
    categoria: str | None = Field(default=None, max_length=40)
    versao: str | None = Field(default=None, max_length=20)
    formatos: list[Literal["VST3", "AU", "AAX", "CLAP", "Standalone"]] = Field(default_factory=list, max_length=5)
    recursos: list[str] = Field(default_factory=list, max_length=12)
    requisitos: str | None = Field(default=None, max_length=2000)
    preco: Decimal = Field(default=Decimal(0), ge=0, le=Decimal("99999.99"), decimal_places=2)
    preco_promocional: Decimal | None = Field(default=None, ge=0, le=Decimal("99999.99"), decimal_places=2)
    video_url: str | None = Field(default=None, max_length=300)
    status: Literal["rascunho", "publicado", "arquivado"] = "rascunho"
    destaque: bool = False
    ordem: int = Field(default=0, ge=0, le=9999)

    @field_validator("slug")
    @classmethod
    def slug_valido(cls, value):
        value = value.lower()
        if not SLUG.match(value):
            raise ValueError("slug_invalido")
        return value

    @field_validator("tagline", "categoria", "versao", "video_url", "descricao", "requisitos")
    @classmethod
    def limpar(cls, value):
        return _clean(value)

    @field_validator("recursos")
    @classmethod
    def recursos_validos(cls, value):
        items = [" ".join(item.split())[:120] for item in value if item and item.strip()]
        return list(dict.fromkeys(items))

    @field_validator("formatos")
    @classmethod
    def formatos_unicos(cls, value):
        return [item for item in FORMATOS if item in value]

    @field_validator("video_url")
    @classmethod
    def video_https(cls, value):
        if value and not value.startswith("https://"):
            raise ValueError("video_https")
        return value

    @model_validator(mode="after")
    def promocao_menor(self):
        if self.preco_promocional is not None and self.preco_promocional >= self.preco:
            raise ValueError("promocao_deve_ser_menor")
        return self


class PluginInstaladorLink(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    link: str = Field(min_length=12, max_length=500)
    versao: str | None = Field(default=None, max_length=20)

    @field_validator("link")
    @classmethod
    def https(cls, value):
        if not value.startswith("https://"):
            raise ValueError("link_https")
        return value


class PluginCortesia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cliente_id: int = Field(gt=0)


class PluginRevogacao(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    motivo: str = Field(min_length=3, max_length=40)


class PluginValidacao(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chave: str = Field(min_length=10, max_length=40)
    plugin: str = Field(min_length=1, max_length=60)
