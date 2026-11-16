import re
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VERSAO = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.\-+]{0,19}$")
CUPOM = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,31}$")


def _text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


class VersaoPayload(BaseModel):
    """A release of a plugin. Publishing a stable release makes it the plugin's current version."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    versao: str = Field(min_length=1, max_length=20)
    canal: Literal["estavel", "beta"] = "estavel"
    notas: str | None = Field(default=None, max_length=8000)
    notas_en: str | None = Field(default=None, max_length=8000)
    obrigatoria: bool = False
    publicar: bool = True

    @field_validator("versao")
    @classmethod
    def versao_valida(cls, value):
        if not VERSAO.match(value):
            raise ValueError("versao_invalida")
        return value

    @field_validator("notas", "notas_en")
    @classmethod
    def limpar(cls, value):
        return _text(value)


class CupomPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    codigo: str = Field(min_length=3, max_length=32)
    descricao: str | None = Field(default=None, max_length=160)
    tipo: Literal["percentual", "valor"]
    valor: Decimal = Field(gt=0, le=Decimal("99999.99"), decimal_places=2)
    plugin_id: int | None = Field(default=None, gt=0)
    valido_de: datetime | None = None
    valido_ate: datetime | None = None
    max_usos: int | None = Field(default=None, gt=0, le=1_000_000)
    ativo: bool = True

    @field_validator("codigo")
    @classmethod
    def codigo_valido(cls, value):
        value = value.upper()
        if not CUPOM.match(value):
            raise ValueError("codigo_invalido")
        return value

    @field_validator("descricao")
    @classmethod
    def limpar(cls, value):
        return _text(value)

    @model_validator(mode="after")
    def coerente(self):
        if self.tipo == "percentual" and self.valor > 100:
            raise ValueError("percentual_ate_100")
        if self.valido_de and self.valido_ate and self.valido_ate <= self.valido_de:
            raise ValueError("periodo_invalido")
        return self


class CupomValidacao(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    codigo: str = Field(min_length=3, max_length=32)
    plugin: str = Field(min_length=1, max_length=60)


class PluginCompra(BaseModel):
    """Optional body of a store purchase."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cupom: str | None = Field(default=None, max_length=32)

    @field_validator("cupom")
    @classmethod
    def normalizar(cls, value):
        value = _text(value)
        return value.upper() if value else None


class BannerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ativo: bool = False
    texto: str | None = Field(default=None, max_length=200)
    texto_en: str | None = Field(default=None, max_length=200)
    link: str | None = Field(default=None, max_length=300)

    @field_validator("texto", "texto_en", "link")
    @classmethod
    def limpar(cls, value):
        return _text(value)

    @field_validator("link")
    @classmethod
    def link_seguro(cls, value):
        if value and not (value.startswith("https://") or (value.startswith("/") and not value.startswith("//"))):
            raise ValueError("link_https_ou_caminho")
        return value

    @model_validator(mode="after")
    def texto_quando_ativo(self):
        if self.ativo and not (self.texto or self.texto_en):
            raise ValueError("banner_sem_texto")
        return self


class OrdemPayload(BaseModel):
    """The store order: plugin ids from first to last, and which are featured."""

    model_config = ConfigDict(extra="forbid")

    ids: list[int] = Field(min_length=1, max_length=500)
    destaques: list[int] = Field(default_factory=list, max_length=500)


class Reembolso(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    motivo: str = Field(min_length=3, max_length=40)


class CortesiaEmail(BaseModel):
    """A courtesy license by e-mail: finds the customer (studio client or Labs account)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=5, max_length=150)

    @field_validator("email")
    @classmethod
    def minusculo(cls, value):
        value = value.lower()
        if "@" not in value:
            raise ValueError("email_invalido")
        return value
