"""Catalog combos (Roadmap 3.0, 5.08)."""
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from schemas.promocao import PrecoCatalogo, Promocao, validar_preco

Money = Annotated[Decimal, Field(ge=0, le=Decimal("9999999999.99"), max_digits=12, decimal_places=2, allow_inf_nan=False)]


class ComboWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=3, max_length=100)
    descricao: str = Field(default="", max_length=1000)
    subtitulo: str = Field(default="", max_length=150)
    preco_base: Money
    aplica_desconto: bool = False
    destaques: list[Annotated[str, Field(max_length=200)]] = Field(default_factory=list, max_length=20)
    ativo: bool = True
    promocao: Promocao | None = None
    servicos: list[Annotated[int, Field(gt=0)]] = Field(min_length=2, max_length=10)

    @model_validator(mode="after")
    def preco_promocional_positivo(self):
        validar_preco(self.preco_base, self.promocao)
        return self

    @field_validator("nome", "descricao", "subtitulo")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("destaques")
    @classmethod
    def clean_highlights(cls, value):
        return [item.strip() for item in value if item.strip()]  # Blank lines are dropped.

    @field_validator("servicos")
    @classmethod
    def unique_services(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("servico_repetido")
        return value


class ComboServico(BaseModel):
    servico_id: int
    nome: str
    valor_base: Decimal
    etapas: int
    # Catalog rework: what each service includes, inherited by the combo.
    estrutura: dict | None = None
    parametros: str = ""
    prazo_estimado_dias: int | None = None


class ComboResponse(BaseModel):
    id: int
    nome: str
    descricao: str
    subtitulo: str = ""
    preco_base: Decimal
    aplica_desconto: bool = False
    destaques: list[str] = []
    parametros: str = ""  # Union of the services' calculator parameters.
    prazo_estimado_dias: int | None = None
    ativo: bool
    promocao: Promocao | None = None
    preco_catalogo: PrecoCatalogo | None = None
    soma_servicos: Decimal
    servicos: list[ComboServico]
    created_at: datetime | None
    updated_at: datetime | None
